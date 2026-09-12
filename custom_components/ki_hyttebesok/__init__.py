"""KI Hyttebesøk – hvem er på hytta, og hvor mye har de vært der."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, PLATFORMS
from .coordinator import HytteMotor


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    motor = HytteMotor(hass, {**entry.data, **entry.options})
    motor.entry = entry
    await motor.start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = motor
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_oppdater))

    async def les(call: ServiceCall) -> None:
        for m in list(hass.data[DOMAIN].values()):
            await m._les_kalender(None)

    async def registrer(call: ServiceCall) -> None:
        """Legg inn et opphold manuelt – for eksempel et du glemte."""
        for m in list(hass.data[DOMAIN].values()):
            if call.data.get("sted") and call.data["sted"].lower() != m.sted.lower():
                continue
            p = next((x for x in m.personer if x.navn.lower() == str(call.data.get("person", "")).lower()), None)
            if p is None:
                continue
            await m.skriv_opphold(p, call.data["fra"], call.data.get("til") or call.data["fra"])
            await m._les_kalender(None)

    hass.services.async_register(DOMAIN, "les_kalender", les)
    hass.services.async_register(DOMAIN, "registrer_opphold", registrer)
    return True


async def _oppdater(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        motor = hass.data[DOMAIN].pop(entry.entry_id)
        await motor.stopp()
    return ok
