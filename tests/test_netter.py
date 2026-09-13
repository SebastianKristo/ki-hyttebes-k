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
