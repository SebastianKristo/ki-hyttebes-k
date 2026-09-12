"""Knapper: tving en synk av kalenderen, og avslutt et opphold manuelt."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTR_INTEGRASJON, ATTR_TYPE, DOMAIN
from .entity import HytteEntitet


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    motor = hass.data[DOMAIN][entry.entry_id]
    add([Synk(motor), LagreNaa(motor)])


class Synk(HytteEntitet, ButtonEntity):
    """Leser kalenderen med en gang i stedet for å vente på kvarteret."""

    _attr_icon = "mdi:calendar-sync"

    def __init__(self, motor) -> None:
        super().__init__(motor, "synk", "Synk kalenderen nå")

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "synk",
                "sist_lest": getattr(self.motor, "sist_lest", None), "feil": self.motor.feil}

    async def async_press(self) -> None:
        await self.motor._les_kalender(None)


class LagreNaa(HytteEntitet, ButtonEntity):
    """Skriver oppholdene som pågår nå til kalenderen, uten å vente på avreise."""

    _attr_icon = "mdi:calendar-plus"

    def __init__(self, motor) -> None:
        super().__init__(motor, "lagre_naa", "Lagre pågående opphold")

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "lagre_naa",
                "paagaar": [p.navn for p in self.motor.her_naa()]}

    async def async_press(self) -> None:
        i_dag = dt_util.now().date().isoformat()
        for p in self.motor.her_naa():
            if p.ankom:
                await self.motor.skriv_opphold(p, p.ankom, i_dag)
        await self.motor._les_kalender(None)
