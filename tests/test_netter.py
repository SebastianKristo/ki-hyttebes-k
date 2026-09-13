"""Netter skal telles på datoen til hver natt, ikke på oppholdets startår."""
from datetime import date
from unittest.mock import MagicMock, patch

from custom_components.ki_hyttebesok.coordinator import HytteMotor, Opphold, Person


def _motor(rolle="hjem"):
    m = HytteMotor(MagicMock(), {"sted": "Oslo", "rolle": rolle})
    m.personer = [Person(navn="Sebastian", entity="switch.seb")]
    return m


def test_blokk_over_nyttar_teller_i_begge_ar():
    m = _motor()
    m.opphold = [Opphold(person="Sebastian", start=date(2025, 8, 9),
                         slutt=date(2026, 9, 13), tittel="Hjemme")]
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.year = 2026
        assert m.netter("Sebastian") == 256          # 1. jan – 13. sep 2026
        assert m.netter("Sebastian", aar=2025) == 145
        assert m.besok("Sebastian") == 1


def test_gammel_feil_ga_null():
    """Regresjonen: startåret var 2025, så 2026 ble 0."""
    m = _motor()
    o = Opphold(person="Sebastian", start=date(2025, 8, 9), slutt=date(2026, 9, 13))
    assert o.start.year != 2026
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.year = 2026
        m.opphold = [o]
        assert m.netter("Sebastian") > 0


def test_hytteopphold_teller_som_for():
    m = _motor("hytte")
    m.personer = [Person(navn="Rune", entity="switch.rune")]
    m.opphold = [Opphold(person="Rune", start=date(2026, 7, 3), slutt=date(2026, 7, 6))]
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.year = 2026
        assert m.netter("Rune") == 4
        assert m.besok("Rune") == 1
        assert m.netter("Rune", aar=2025) == 0


def test_stromstad_med_o_og_oe_er_samme_sted():
    """Den svenske instansen skriver «Strömstad», Oslo har stedet som «Strømstad»."""
    from custom_components.ki_hyttebesok.coordinator import nokkel
    assert nokkel("Strömstad") == nokkel("Strømstad")
    assert nokkel("Strömstad") in nokkel("Strömstad – Rune")
    assert nokkel("Strømstad") in nokkel("Strömstad – Rune")
    assert nokkel("Toten") not in nokkel("Strömstad – Rune")


def test_personnavn_taler_samme_forskjell():
    from custom_components.ki_hyttebesok.coordinator import nokkel
    assert nokkel("Sebastian") == nokkel("sebastian")
    assert nokkel("Cybele") in nokkel("Toten – Cybele")


def test_slug_er_uendret_for_vanlige_navn():
    from custom_components.ki_hyttebesok.coordinator import Person
    assert Person(navn="Rune", entity="").slug == "rune"
    assert Person(navn="Cybele", entity="").slug == "cybele"


def test_stedsnavn_blir_ikke_en_person():
    """«Strömstad» alene i tittelen skal ikke gi en person som heter Strömstad."""
    m = _motor("hytte")
    m.sted = "Strömstad"
    assert m._person_i("Strömstad", {}) == ""
    assert m._person_i("Strömstad – Strömstad", {}) == ""
    assert m._person_i("Strömstad – Rune", {}) == "Rune"
    assert m._person_i("Strömstad - Cybele", {}) == "Cybele"
    assert m._person_i("Strömstad: Sebastian", {}) == "Sebastian"


def test_kjent_person_vinner_over_reservenavnet():
    from custom_components.ki_hyttebesok.coordinator import nokkel
    m = _motor("hytte")
    m.sted = "Strömstad"
    kjente = {nokkel("Rune"): Person(navn="Rune", entity="switch.rune")}
    assert m._person_i("Strömstad – rune", kjente) == "Rune"


def test_opphold_uten_navn_teller_fortsatt_for_stedet():
    m = _motor("hytte")
    m.opphold = [Opphold(person="", start=date(2026, 5, 1), slutt=date(2026, 5, 2))]
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.year = 2026
        assert m.netter() == 2
        assert m.opphold[0].som_dict()["person"] == "Ukjent"


def _sett_opp(m, kalenderopphold, hytteopphold=None):
    """Kjører hjemme-valget slik _les_kalender gjør, uten å gå via kalender-API-et."""
    from custom_components.ki_hyttebesok.const import CONF_HJEMME_KILDE, KILDE_AUTO
    from custom_components.ki_hyttebesok.coordinator import ROLLE_HJEM
    opphold = list(kalenderopphold)
    m.hjemme_kilde = ""
    if m.rolle == ROLLE_HJEM and m.personer:
        valg = m.oppsett.get(CONF_HJEMME_KILDE) or KILDE_AUTO
        if valg == "fravaer" or (valg == KILDE_AUTO and not opphold):
            opphold = hytteopphold or []
            m.hjemme_kilde = "fravaer"
        else:
            m.hjemme_kilde = "kalender"
    m.opphold = opphold
    return m


def test_auto_vipper_nar_forste_hjemmehendelse_kommer():
    """Regresjonen: én hendelse i kalenderen tok Oslo fra hundrevis av netter til 1."""
    avledet = [Opphold(person="Cybele", start=date(2026, 1, 1), slutt=date(2026, 9, 1))]
    tom = _sett_opp(_motor("hjem"), [], avledet)
    assert tom.hjemme_kilde == "fravaer"

    en_hendelse = [Opphold(person="Cybele", start=date(2026, 9, 12), slutt=date(2026, 9, 12))]
    med = _sett_opp(_motor("hjem"), en_hendelse, avledet)
    assert med.hjemme_kilde == "kalender"


def test_fravaer_star_fast_selv_med_hendelser():
    m = _motor("hjem")
    m.oppsett["hjemme_kilde"] = "fravaer"
    avledet = [Opphold(person="Cybele", start=date(2026, 1, 1), slutt=date(2026, 9, 1))]
    _sett_opp(m, [Opphold(person="Cybele", start=date(2026, 9, 12), slutt=date(2026, 9, 12))], avledet)
    assert m.hjemme_kilde == "fravaer"
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.year = 2026
        assert m.netter("Cybele") > 200


def test_ny_person_i_kalenderen_utloser_omlasting():
    """Personsensorene lages én gang – dukker noen opp senere, må oppføringen lastes på nytt."""
    m = _motor("hytte")
    m.entry = MagicMock(entry_id="abc")
    m.hass = MagicMock()
    m._klar = True
    m.personer = [Person(navn="Rune", entity="")]
    m._sjekk_nye_personer({"Rune"})
    m.hass.config_entries.async_schedule_reload.assert_not_called()

    m.personer = [Person(navn="Rune", entity=""), Person(navn="Cybele", entity="")]
    m._sjekk_nye_personer({"Rune"})
    m.hass.config_entries.async_schedule_reload.assert_called_once_with("abc")


def test_ingen_omlasting_for_plattformene_er_klare():
    m = _motor("hytte")
    m.entry = MagicMock(entry_id="abc")
    m.hass = MagicMock()
    m._klar = False
    m.personer = [Person(navn="Cybele", entity="")]
    m._sjekk_nye_personer(set())
    m.hass.config_entries.async_schedule_reload.assert_not_called()


def test_omlasting_skjer_bare_en_gang():
    m = _motor("hytte")
    m.entry = MagicMock(entry_id="abc")
    m.hass = MagicMock()
    m._klar = True
    m.personer = [Person(navn="Cybele", entity="")]
    m._sjekk_nye_personer(set())
    m.personer.append(Person(navn="Sebastian", entity=""))
    m._sjekk_nye_personer({"Cybele"})
    assert m.hass.config_entries.async_schedule_reload.call_count == 1


def _person(m, navn="Sebastian", eid="switch.seb", ankom="2026-09-10"):
    p = Person(navn=navn, entity=eid)
    p.ankom = ankom
    m.personer = [p]
    return p


def test_kort_tur_ut_avslutter_ikke_oppholdet():
    """Bryteren av i ti minutter skal ikke slå «Her nå» til null."""
    from datetime import datetime, timezone
    m = _motor("hjem")
    m.oppsett["forsinkelse"] = 30
    p = _person(m)
    st = MagicMock(state="off", last_changed=datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc))
    m.hass.states.get.return_value = st
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.utcnow.return_value = datetime(2026, 9, 13, 12, 10, tzinfo=timezone.utc)
        assert m._pa_stedet(p) is True          # borte i 10 min av 30
        dt.utcnow.return_value = datetime(2026, 9, 13, 12, 45, tzinfo=timezone.utc)
        assert m._pa_stedet(p) is False         # borte i 45 min


def test_bryter_pa_er_alltid_her():
    m = _motor("hjem")
    p = _person(m)
    m.hass.states.get.return_value = MagicMock(state="on", last_changed=None)
    assert m._pa_stedet(p) is True


def test_manglende_bryter_faller_tilbake_pa_kalenderen():
    """Instanser uten stedets brytere skal spørre kalenderen, ikke svare «borte»."""
    m = _motor("hytte")
    p = _person(m, navn="Rune", eid="switch.finnes_ikke", ankom=None)
    m.hass.states.get.return_value = None
    m.opphold = [Opphold(person="Rune", start=date(2026, 9, 12), slutt=date(2026, 9, 14))]
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.date.return_value = date(2026, 9, 13)
        assert m._pa_stedet(p) is True


def test_utilgjengelig_bryter_teller_ikke_som_borte():
    m = _motor("hytte")
    p = _person(m, navn="Rune", eid="switch.rune", ankom=None)
    m.hass.states.get.return_value = MagicMock(state="unavailable", last_changed=None)
    m.opphold = []
    with patch("custom_components.ki_hyttebesok.coordinator.dt_util") as dt:
        dt.now.return_value.date.return_value = date(2026, 9, 13)
        assert m._pa_stedet(p) is False        # ingen kalenderdekning heller
