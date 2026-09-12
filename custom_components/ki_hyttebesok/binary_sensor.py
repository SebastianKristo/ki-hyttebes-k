"""Er det noen på stedet?"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_INTEGRASJON, ATTR_TYPE, DOMAIN
from .entity import HytteEntitet


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([NoenHer(hass.data[DOMAIN][entry.entry_id])])


class NoenHer(HytteEntitet, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_icon = "mdi:home-account"

    def __init__(self, motor) -> None:
        super().__init__(motor, "noen_her", "Noen på stedet")

    @property
    def is_on(self) -> bool:
        return bool(self.motor.her_naa())

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN, ATTR_TYPE: "noen_her",
                "personer": [p.navn for p in self.motor.her_naa()]}
