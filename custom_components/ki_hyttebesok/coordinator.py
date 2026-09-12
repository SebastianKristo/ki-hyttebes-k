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

from .const import CONF_FORSINKELSE, CONF_HISTORIKK, DOMAIN, FARGER, STD_FORSINKELSE, STD_HISTORIKK

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
        st = self.hass.states.get(p.entity)
        return bool(st and st.state in ("on", "home", "true"))

    def her_naa(self) -> list[Person]:
        return [p for p in self.personer if self._pa_stedet(p)]

    @callback
    def _endret(self, hendelse) -> None:
        self.hass.async_create_task(self._behandle(hendelse))

    async def _behandle(self, hendelse) -> None:
        """Ankomst starter et opphold, avreise skriver det til kalenderen."""
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
        self.opphold, self.kommende = opphold, kommende
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

    def oversikt(self) -> dict[str, Any]:
        nå = dt_util.now().date()
        fra, til = nå - timedelta(days=200), nå + timedelta(days=200)
        her = self.her_naa()
        return {
            "sted": self.sted, "kalender": self.kalender,
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
