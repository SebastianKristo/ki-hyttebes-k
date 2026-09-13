"""Oppsett: sted, kalender og hvem som skal telles."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_FORSINKELSE,
    CONF_ROLLE,
    CONF_SKRIV,
    CONF_HISTORIKK,
    CONF_KALENDER,
    CONF_PERSONER,
    CONF_STED,
    CONF_HJEMME_KILDE,
    DOMAIN,
    KILDE_AUTO,
    STD_FORSINKELSE,
    STD_HISTORIKK,
)


def _skjema(d: dict[str, Any] | None = None) -> vol.Schema:
    d = d or {}
    return vol.Schema({
        vol.Required(CONF_STED, default=d.get(CONF_STED, "")): str,
        vol.Required(CONF_ROLLE, default=d.get(CONF_ROLLE, "hytte")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[
                {"value": "hjem", "label": "Hjemme"}, {"value": "hytte", "label": "Hytte"}], mode="list")),
        vol.Required(CONF_KALENDER, default=d.get(CONF_KALENDER, "")): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="calendar")),
        vol.Optional("brytere", default=[p.get("entity") for p in (d.get(CONF_PERSONER) or [])]):
            selector.EntitySelector(selector.EntitySelectorConfig(
                domain=["switch", "binary_sensor", "input_boolean", "person", "device_tracker"], multiple=True)),
        vol.Optional("navn", default=", ".join(p.get("navn", "") for p in (d.get(CONF_PERSONER) or []))): str,
        vol.Optional(CONF_HJEMME_KILDE, default=d.get(CONF_HJEMME_KILDE, KILDE_AUTO)): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[
                {"value": "auto", "label": "Auto – kalenderen hvis den har hendelser, ellers fravær"},
                {"value": "fravaer", "label": "Fravær – alle netter ingen var på en hytte"},
                {"value": "kalender", "label": "Kalender – bare det som er skrevet"}], mode="dropdown")),
        vol.Optional(CONF_SKRIV, default=d.get(CONF_SKRIV, bool(d.get(CONF_PERSONER)))): bool,
        vol.Optional(CONF_FORSINKELSE, default=d.get(CONF_FORSINKELSE, STD_FORSINKELSE)): vol.Coerce(int),
        vol.Optional(CONF_HISTORIKK, default=d.get(CONF_HISTORIKK, STD_HISTORIKK)): vol.Coerce(int),
    })


def _personer(user_input: dict[str, Any]) -> list[dict[str, Any]]:
    """Kobler bryterne med navnene som er skrevet inn, i samme rekkefølge."""
    navn = [n.strip() for n in str(user_input.get("navn") or "").split(",")]
    ut = []
    for i, e in enumerate(user_input.get("brytere") or []):
        ut.append({"entity": e, "navn": navn[i] if i < len(navn) and navn[i] else ""})
    return ut


class KiHytteFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_STED].lower()}")
            self._abort_if_unique_id_configured()
            data = {k: v for k, v in user_input.items() if k not in ("brytere", "navn")}
            data[CONF_PERSONER] = _personer(user_input)
            return self.async_create_entry(title=f"KI Hyttebesøk {user_input[CONF_STED]}", data=data)
        return self.async_show_form(step_id="user", data_schema=_skjema())

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return KiHytteOptions(entry)


class KiHytteOptions(config_entries.OptionsFlow):
    def __init__(self, entry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            data = {k: v for k, v in user_input.items() if k not in ("brytere", "navn")}
            data[CONF_PERSONER] = _personer(user_input)
            return self.async_create_entry(title="", data=data)
        return self.async_show_form(step_id="init", data_schema=_skjema({**self.entry.data, **self.entry.options}))
