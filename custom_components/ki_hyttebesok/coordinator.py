"""Motoren i KI Hyttebesøk.

Følger med på hvem som er på stedet, skriver opphold til Google-kalenderen når
noen drar, og leser kalenderen tilbake for historikk og statistikk. Alle stedene
kan dele samme kalender – hendelsene merkes med stedsnavnet.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FORSINKELSE,
    CONF_SKRIV,
    CONF_HISTORIKK,
    CONF_ROLLE,
    DOMAIN,
    FARGER,
    ROLLE_HJEM,
    STD_FORSINKELSE,
    STD_HISTORIKK,
)

_LOGGER = logging.getLogger(__name__)

LES_INTERVALL = timedelta(minutes=15)
MAANEDER = ["januar", "februar", "mars", "april", "mai", "juni",
            "juli", "august", "september", "oktober", "november", "desember"]


@dataclass
class Person:
    """En i husstanden, med bryteren som sier om hen er på stedet."""

    navn: str
    entity: str
    farge: str = "var(--green)"
    ankom: str | None = None          # ISO-dato for start på gjeldende opphold
    _siden: datetime | None = None

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "_", self.navn.lower().replace("ø", "o").replace("æ", "a").replace("å", "a")).strip("_")


@dataclass
class Opphold:
    """Ett besøk hentet fra kalenderen."""

    person: str
    start: date
    slutt: date                       # siste natt (kalenderens sluttdato minus én dag)
    tittel: str = ""

    @property
    def netter(self) -> int:
        return max(1, (self.slutt - self.start).days + 1)

    def som_dict(self) -> dict[str, Any]:
        return {"person": self.person, "start": self.start.isoformat(), "slutt": self.slutt.isoformat(),
                "netter": self.netter, "tittel": self.tittel}


class HytteMotor:
    """Holder oversikt over ett sted."""

    def __init__(self, hass: HomeAssistant, oppsett: dict[str, Any]) -> None:
        self.hass = hass
        self.oppsett = oppsett
        self.sted: str = oppsett.get("sted") or "Hytta"
        self.rolle: str = oppsett.get(CONF_ROLLE) or "hytte"   # hjem | hytte
        # Med flere Home Assistant-instanser er det bare den som står på stedet
        # som registrerer opphold. De andre leser de samme hendelsene.
        self.skriver: bool = (oppsett.get(CONF_SKRIV)
                              if oppsett.get(CONF_SKRIV) is not None
                              else bool(oppsett.get("personer")))
        self.kalender: str = oppsett.get("kalender") or ""
        self.personer: list[Person] = []
        self.opphold: list[Opphold] = []
        self.kommende: list[dict[str, Any]] = []
        self.feil: str | None = None
        self.sist_lest: str | None = None
        self._av: list[Any] = []
        self._lyttere: list[Any] = []
        self._lager = Store(hass, 1, f"{DOMAIN}_{re.sub(r'[^a-z0-9]+', '_', self.sted.lower())}")

    # ------------------------------------------------------------------ start
    async def start(self) -> None:
        if not (self.oppsett.get("personer") or []):
            await self._les_kalender(None)      # navnene kommer fra hendelsene
        self._les_personer()
        lagret = await self._lager.async_load() or {}
        for p in self.personer:
            p.ankom = (lagret.get("ankom") or {}).get(p.slug)
        fulgte = [p.entity for p in self.personer if p.entity]
        if fulgte:
            self._av.append(async_track_state_change_event(self.hass, fulgte, self._endret))
        self._av.append(async_track_time_interval(self.hass, self._les_kalender, LES_INTERVALL))
        await self._les_kalender(None)

    async def stopp(self) -> None:
        for av in self._av:
            av()
        self._av.clear()
        await self._lagre()

    def abonner(self, cb) -> Any:
        self._lyttere.append(cb)

        def av() -> None:
            if cb in self._lyttere:
                self._lyttere.remove(cb)
        return av

    def _varsle(self) -> None:
        for cb in list(self._lyttere):
            cb()

    def _les_personer(self) -> None:
        self.personer = []
        if not (self.oppsett.get("personer") or []):
            # ingen brytere: navnene kommer fra kalenderhendelsene
            navn = []
            for o in self.opphold:
                if o.person not in navn:
                    navn.append(o.person)
            for k in self.kommende:
                if k.get("person") and k["person"] not in navn:
                    navn.append(k["person"])
            for i, n in enumerate(navn):
                self.personer.append(Person(navn=n, entity="", farge=FARGER[i % len(FARGER)]))
            return
        for i, rad in enumerate(self.oppsett.get("personer") or []):
            if isinstance(rad, str):
                rad = {"entity": rad}
            eid = rad.get("entity")
            if not eid:
                continue
            st = self.hass.states.get(eid)
            navn = rad.get("navn") or (st.attributes.get("friendly_name") if st else None) or eid.split(".")[-1]
            navn = re.sub(r"\s*(posisjon|hjemme|borte).*$", "", navn, flags=re.I).strip().title() or navn
            self.personer.append(Person(navn=navn, entity=eid, farge=rad.get("farge") or FARGER[i % len(FARGER)]))

    async def _lagre(self) -> None:
        await self._lager.async_save({"ankom": {p.slug: p.ankom for p in self.personer if p.ankom}})

    # ------------------------------------------------------------ tilstedeværelse
    def _pa_stedet(self, p: Person) -> bool:
        """Hvert sted har sine egne posisjonsbrytere: på = her, av = borte.
        Steder denne instansen bare leser, avgjøres av kalenderen."""
        if not p.entity:
            return self._i_kalenderen(p.navn)
        st = self.hass.states.get(p.entity)
        return bool(st and st.state in ("on", "home", "true"))

    def _i_kalenderen(self, navn: str) -> bool:
        """Er personen registrert her i dag, ifølge kalenderen?"""
        i_dag = dt_util.now().date()
        return any(o.start <= i_dag <= o.slutt and o.person.lower() == str(navn).lower()
                   for o in self.opphold)

    def her_naa(self) -> list[Person]:
        return [p for p in self.personer if self._pa_stedet(p)]

    def _paa_hytte_i_dag(self) -> set[str]:
        """Hvem kalenderen sier er på en av hyttene akkurat nå."""
        ut: set[str] = set()
        i_dag = dt_util.now().date()
        for m in self.hass.data.get(DOMAIN, {}).values():
            if m is self or m.rolle == ROLLE_HJEM:
                continue
            for o in m.opphold:
                if o.start <= i_dag <= o.slutt:
                    ut.add(o.person)
        return ut

    @callback
    def _endret(self, hendelse) -> None:
        self.hass.async_create_task(self._behandle(hendelse))

    async def _behandle(self, hendelse) -> None:
        """Ankomst starter et opphold, avreise skriver det til kalenderen.
        Gjelder bare steder som har egne brytere – hyttene leses fra kalenderen."""
        if not self.skriver:
            return
        eid = hendelse.data.get("entity_id")
        ny = hendelse.data.get("new_state")
        p = next((x for x in self.personer if x.entity == eid), None)
        if not p or ny is None:
            return
        minutter = int(self.oppsett.get(CONF_FORSINKELSE) or STD_FORSINKELSE)
        pa = ny.state in ("on", "home", "true")
        if pa:
            if not p.ankom:
                p.ankom = dt_util.now().date().isoformat()
                await self._lagre()
                self._varsle()
            return
        # dro
        if not p.ankom:
            return
        sist = ny.last_changed or dt_util.utcnow()
        if (dt_util.utcnow() - sist).total_seconds() < minutter * 60:
            return
        await self.skriv_opphold(p, p.ankom, dt_util.now().date().isoformat())
        p.ankom = None
        await self._lagre()
        await self._les_kalender(None)

    async def skriv_opphold(self, p: Person, fra: str, til: str) -> None:
        """Lager en heldagshendelse i kalenderen. Sluttdato er eksklusiv."""
        if not self.kalender:
            return
        try:
            slutt = date.fromisoformat(til) + timedelta(days=1)
            await self.hass.services.async_call("calendar", "create_event", {
                "entity_id": self.kalender,
                "summary": f"{self.sted} – {p.navn}",
                "start_date": fra,
                "end_date": slutt.isoformat(),
            }, blocking=True)
            _LOGGER.debug("KI Hyttebesøk: skrev %s %s–%s", p.navn, fra, til)
        except Exception as feil:  # noqa: BLE001
            self.feil = str(feil)
            _LOGGER.warning("KI Hyttebesøk: klarte ikke skrive til kalenderen: %s", feil)

    # ------------------------------------------------------------------ kalender
    async def _les_kalender(self, _nå) -> None:
        if not self.kalender:
            return
        nå = dt_util.now()
        start = nå - timedelta(days=int(self.oppsett.get(CONF_HISTORIKK) or STD_HISTORIKK))
        slutt = nå + timedelta(days=365)
        try:
            svar = await self.hass.services.async_call("calendar", "get_events", {
                "entity_id": self.kalender,
                "start_date_time": start.isoformat(),
                "end_date_time": slutt.isoformat(),
            }, blocking=True, return_response=True)
        except Exception as feil:  # noqa: BLE001
            self.feil = str(feil)
            return
        self.feil = None
        self.sist_lest = dt_util.now().isoformat(timespec="minutes")
        hendelser = (svar or {}).get(self.kalender, {}).get("events", [])
        opphold: list[Opphold] = []
        kommende: list[dict[str, Any]] = []
        navn = {p.navn.lower(): p for p in self.personer}
        for h in hendelser:
            tittel = str(h.get("summary") or "")
            if self.sted and self.sted.lower() not in tittel.lower():
                continue                      # hendelser for andre steder i samme kalender
            s = _dato(h.get("start"))
            e = _dato(h.get("end"))
            if not s:
                continue
            siste = (e - timedelta(days=1)) if e and e > s else s
            hvem = next((p.navn for k, p in navn.items() if k in tittel.lower()), tittel.split("–")[-1].strip())
            if s > nå.date():
                kommende.append({"person": hvem, "start": s.isoformat(), "slutt": siste.isoformat(),
                                 "netter": max(1, (siste - s).days + 1), "tittel": tittel})
            else:
                opphold.append(Opphold(person=hvem, start=s, slutt=siste, tittel=tittel))
        opphold.sort(key=lambda x: x.start, reverse=True)
        kommende.sort(key=lambda x: x["start"])
        # Hjemme uten egne hendelser: regn oppholdene som dagene ingen hytte dekker.
        # Dette er reserven for oppsett der hjemmet ikke føres i kalenderen.
        if self.rolle == ROLLE_HJEM and not opphold and self.personer:
            opphold = self._hjemmeopphold()
        self.opphold, self.kommende = opphold, kommende
        if not (self.oppsett.get("personer") or []):
            self._les_personer()
        self._varsle()

    # ------------------------------------------------------------------ tall ut
    def netter(self, person: str | None = None, aar: int | None = None) -> int:
        aar = aar or dt_util.now().year
        return sum(o.netter for o in self.opphold
                   if o.start.year == aar and (person is None or o.person.lower() == person.lower()))

    def besok(self, person: str | None = None, aar: int | None = None) -> int:
        aar = aar or dt_util.now().year
        return len([o for o in self.opphold
                    if o.start.year == aar and (person is None or o.person.lower() == person.lower())])

    def siste(self, person: str | None = None) -> Opphold | None:
        for o in self.opphold:
            if person is None or o.person.lower() == person.lower():
                return o
        return None

    def per_maaned(self, aar: int | None = None) -> list[dict[str, Any]]:
        """Netter per måned, til søylene i kortet."""
        aar = aar or dt_util.now().year
        ut = [{"maaned": m, "navn": MAANEDER[m - 1], "netter": 0, "personer": {}} for m in range(1, 13)]
        for o in self.opphold:
            d = o.start
            for i in range(o.netter):
                dag = d + timedelta(days=i)
                if dag.year != aar:
                    continue
                rad = ut[dag.month - 1]
                rad["netter"] += 1
                rad["personer"][o.person] = rad["personer"].get(o.person, 0) + 1
        return ut

    def dager(self, fra: date, til: date) -> dict[str, list[str]]:
        """Hvilke personer som var der hver dag – kalenderrutenettet i kortet."""
        ut: dict[str, list[str]] = {}
        for o in self.opphold + [Opphold(person=k["person"], start=date.fromisoformat(k["start"]),
                                         slutt=date.fromisoformat(k["slutt"]), tittel=k["tittel"])
                                 for k in self.kommende]:
            for i in range(o.netter):
                dag = o.start + timedelta(days=i)
                if fra <= dag <= til:
                    ut.setdefault(dag.isoformat(), [])
                    if o.person not in ut[dag.isoformat()]:
                        ut[dag.isoformat()].append(o.person)
        # de som er her akkurat nå, men ikke skrevet til kalenderen ennå
        for p in self.her_naa():
            start = date.fromisoformat(p.ankom) if p.ankom else dt_util.now().date()
            dag = start
            while dag <= dt_util.now().date():
                if fra <= dag <= til:
                    ut.setdefault(dag.isoformat(), [])
                    if p.navn not in ut[dag.isoformat()]:
                        ut[dag.isoformat()].append(p.navn)
                dag += timedelta(days=1)
        return ut

    def _hjemmeopphold(self) -> list[Opphold]:
        """Hjemme har ingen kalenderhendelser – oppholdene er dagene
        personen ikke var registrert på en hytte."""
        dager = int(self.oppsett.get(CONF_HISTORIKK) or STD_HISTORIKK)
        nå = dt_util.now().date()
        start = nå - timedelta(days=dager)
        borte: dict[str, set[date]] = {}
        for m in self.hass.data.get(DOMAIN, {}).values():
            if m is self or m.rolle == ROLLE_HJEM:
                continue
            for o in m.opphold:
                for i in range(o.netter):
                    d = o.start + timedelta(days=i)
                    if start <= d <= nå:
                        borte.setdefault(o.person, set()).add(d)
        ut: list[Opphold] = []
        for p in self.personer:
            ute = borte.get(p.navn, set())
            d = start
            blokk: date | None = None
            forrige: date | None = None
            while d <= nå:
                hjemme = d not in ute
                if hjemme and blokk is None:
                    blokk = d
                if not hjemme and blokk is not None:
                    ut.append(Opphold(person=p.navn, start=blokk, slutt=forrige or blokk, tittel="Hjemme"))
                    blokk = None
                if hjemme:
                    forrige = d
                d += timedelta(days=1)
            if blokk is not None:
                ut.append(Opphold(person=p.navn, start=blokk, slutt=nå, tittel="Hjemme"))
        ut.sort(key=lambda x: x.start, reverse=True)
        return ut

    def oversikt(self) -> dict[str, Any]:
        nå = dt_util.now().date()
        fra, til = nå - timedelta(days=200), nå + timedelta(days=200)
        her = self.her_naa()
        return {
            "sted": self.sted, "rolle": self.rolle, "skriver": self.skriver, "kalender": self.kalender,
            "her_naa": [{"navn": p.navn, "farge": p.farge, "siden": p.ankom} for p in her],
            "personer": [{
                "navn": p.navn, "farge": p.farge, "entity": p.entity, "her": self._pa_stedet(p),
                "siden": p.ankom,
                "netter_i_aar": self.netter(p.navn), "besok_i_aar": self.besok(p.navn),
                "siste": self.siste(p.navn).som_dict() if self.siste(p.navn) else None,
            } for p in self.personer],
            "netter_i_aar": self.netter(), "besok_i_aar": self.besok(),
            "siste": self.siste().som_dict() if self.siste() else None,
            "kommende": self.kommende[:12],
            "opphold": [o.som_dict() for o in self.opphold[:40]],
            "per_maaned": self.per_maaned(),
            "dager": self.dager(fra, til),
            "feil": self.feil, "sist_lest": self.sist_lest,
        }


def hvem_hvor(motorer: list["HytteMotor"], dag: date) -> dict[str, str]:
    """Hvor hver person var en bestemt dag. Hytteoppholdene teller først,
    og den som ikke var på noen hytte regnes som hjemme."""
    ut: dict[str, str] = {}
    hjem = next((m for m in motorer if m.rolle == ROLLE_HJEM), None)
    for m in motorer:
        if m.rolle == ROLLE_HJEM:
            continue
        for o in m.opphold:
            if o.start <= dag <= o.slutt:
                ut[o.person] = m.sted
        # opphold som pågår nå og ikke er skrevet til kalenderen ennå
        for p in m.her_naa():
            start = date.fromisoformat(p.ankom) if p.ankom else dt_util.now().date()
            if start <= dag <= dt_util.now().date():
                ut[p.navn] = m.sted
    if hjem:
        for p in hjem.personer:
            ut.setdefault(p.navn, hjem.sted)
    return ut


def helger(motorer: list["HytteMotor"], antall: int = 16) -> list[dict[str, Any]]:
    """De siste helgene: hvem som var hvor lørdag og søndag.
    «Uke 32» er ukenummeret lørdagen hører til."""
    nå = dt_util.now().date()
    # nærmeste lørdag bakover
    lordag = nå - timedelta(days=(nå.weekday() - 5) % 7)
    ut: list[dict[str, Any]] = []
    for i in range(antall):
        lor = lordag - timedelta(weeks=i)
        son = lor + timedelta(days=1)
        per_person: dict[str, str] = {}
        for person, sted in hvem_hvor(motorer, lor).items():
            per_person[person] = sted
        for person, sted in hvem_hvor(motorer, son).items():
            if person in per_person and per_person[person] != sted:
                per_person[person] = f"{per_person[person]} → {sted}"
            else:
                per_person.setdefault(person, sted)
        steder: dict[str, list[str]] = {}
        for person, sted in per_person.items():
            steder.setdefault(sted, []).append(person)
        ut.append({
            "uke": lor.isocalendar()[1], "aar": lor.isocalendar()[0],
            "lordag": lor.isoformat(), "sondag": son.isoformat(),
            "personer": per_person, "steder": steder,
            "sammen": len(steder) == 1,
            "hovedsted": max(steder, key=lambda k: len(steder[k])) if steder else None,
        })
    return ut


def _dato(x: Any) -> date | None:
    """Kalenderen gir enten dato eller tidspunkt."""
    if not x:
        return None
    tekst = str(x)
    try:
        if len(tekst) <= 10:
            return date.fromisoformat(tekst[:10])
        d = dt_util.parse_datetime(tekst)
        return dt_util.as_local(d).date() if d else None
    except ValueError:
        return None
