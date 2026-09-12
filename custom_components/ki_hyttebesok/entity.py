"""Felles grunnlag for entitetene."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import ATTR_INTEGRASJON, DOMAIN


class HytteEntitet(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, motor, nokkel: str, navn: str) -> None:
        self.motor = motor
        slug = motor.sted.lower().replace(" ", "_")
        self._attr_unique_id = f"{DOMAIN}_{slug}_{nokkel}"
        self._attr_name = navn
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, slug)}, name=f"KI Hyttebesøk {motor.sted}",
            manufacturer="KI", model="Besøkslogg",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.motor.abonner(self.async_write_ha_state))

    @property
    def extra_state_attributes(self) -> dict:
        return {ATTR_INTEGRASJON: DOMAIN}
