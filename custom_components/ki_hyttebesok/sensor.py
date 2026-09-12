"""Sensorene i KI Hyttebesøk."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTR_INTEGRASJON, ATTR_TYPE, DOMAIN, ROLLE_HJEM
from .coordinator import helger, hvem_hvor
from .entity import HytteEntitet


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    motor = hass.data[DOMAIN][entry.entry_id]
    ut: list[SensorEntity] = [Oversikt(motor), Netter(motor), Siste(motor), Neste(motor), HerNaa(motor)]
    # helgeoversikten lages av hjemme-oppføringen, eller av den første hvis ingen er merket
    alle = list(hass.data[DOMAIN].values())
    hjem = next((m for m in alle if m.rolle == ROLLE_HJEM), alle[0] if alle else None)
    if hjem is motor:
        ut.append(Helger(motor, hass))
    for p in motor.personer:
        ut.append(PersonNetter(motor, p))
    add(ut)


class Oversikt(HytteEntitet, SensorEntity):
    """Alt kortet trenger, i attributtene."""

    _attr_icon = "mdi:home-heart"

    def __init__(self, motor) -> None:
        super().__init__(motor, "oversikt", "Oversikt")

    @property
    def native_value(self) -> str:
        her = self.motor.her_naa()
        return ", ".join(p.navn for p in her) if her else "Tomt"

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "oversikt", **self.motor.oversikt()}


class Netter(HytteEntitet, SensorEntity):
    _attr_native_unit_of_measurement = "netter"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:weather-night"

    def __init__(self, motor) -> None:
        super().__init__(motor, "netter_i_aar", "Netter i år")

    @property
    def native_value(self) -> int:
        return self.motor.netter()

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "netter", "besok": self.motor.besok(),
                "per_maaned": self.motor.per_maaned()}


class PersonNetter(HytteEntitet, SensorEntity):
    _attr_native_unit_of_measurement = "netter"
    _attr_icon = "mdi:account"

    def __init__(self, motor, person) -> None:
        super().__init__(motor, f"netter_{person.slug}", f"Netter {person.navn}")
        self.person = person

    @property
    def native_value(self) -> int:
        return self.motor.netter(self.person.navn)

    @property
    def extra_state_attributes(self) -> dict:
        s = self.motor.siste(self.person.navn)
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "person", "person": self.person.navn,
                "farge": self.person.farge, "her": self.motor._pa_stedet(self.person),
                "siden": self.person.ankom, "besok_i_aar": self.motor.besok(self.person.navn),
                "siste": s.som_dict() if s else None}


class Siste(HytteEntitet, SensorEntity):
    _attr_icon = "mdi:history"

    def __init__(self, motor) -> None:
        super().__init__(motor, "siste_besok", "Siste besøk")

    @property
    def native_value(self) -> str:
        s = self.motor.siste()
        return f"{s.person} {s.start.strftime('%-d. %b')}" if s else "—"

    @property
    def extra_state_attributes(self) -> dict:
        s = self.motor.siste()
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "siste", **(s.som_dict() if s else {}),
                "opphold": [o.som_dict() for o in self.motor.opphold[:20]]}


class Neste(HytteEntitet, SensorEntity):
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, motor) -> None:
        super().__init__(motor, "neste_besok", "Neste besøk")

    @property
    def native_value(self) -> str:
        k = self.motor.kommende
        return f"{k[0]['person']} {k[0]['start']}" if k else "—"

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "neste", "kommende": self.motor.kommende}


class HerNaa(HytteEntitet, SensorEntity):
    _attr_icon = "mdi:account-group"

    def __init__(self, motor) -> None:
        super().__init__(motor, "her_naa", "Her nå")

    @property
    def native_value(self) -> int:
        return len(self.motor.her_naa())

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "her",
                "personer": [p.navn for p in self.motor.her_naa()]}


class Helger(HytteEntitet, SensorEntity):
    """Hvor var vi i helgene? Ser på alle stedene under ett."""

    _attr_icon = "mdi:calendar-weekend"

    def __init__(self, motor, hass) -> None:
        super().__init__(motor, "helger", "Helger")
        self.hass_ref = hass

    def _motorer(self) -> list:
        return list(self.hass_ref.data[DOMAIN].values())

    @property
    def native_value(self) -> str:
        rader = helger(self._motorer(), 1)
        if not rader:
            return "—"
        r = rader[0]
        return r["hovedsted"] or "—"

    @property
    def extra_state_attributes(self) -> dict:
        rader = helger(self._motorer(), 16)
        i_dag = hvem_hvor(self._motorer(), dt_util.now().date())
        return {
            ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "helger",
            "helger": rader,
            "hvor_er_vi_naa": i_dag,
            "steder": [{"sted": m.sted, "rolle": m.rolle} for m in self._motorer()],
            "personer": sorted({p.navn for m in self._motorer() for p in m.personer}),
        }
