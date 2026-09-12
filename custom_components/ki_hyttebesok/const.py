"""Konstanter for KI Hyttebesøk."""
from __future__ import annotations

DOMAIN = "ki_hyttebesok"
PLATFORMS = ["sensor", "binary_sensor"]

CONF_STED = "sted"                # Strömstad, Toten, Oslo …
CONF_KALENDER = "kalender"        # calendar.helge_hus
CONF_PERSONER = "personer"        # [{navn, entity, farge}]
CONF_FORSINKELSE = "forsinkelse"  # minutter før et opphold regnes som reelt
CONF_HISTORIKK = "historikk"      # hvor mange dager bakover vi leser kalenderen

STD_FORSINKELSE = 10
STD_HISTORIKK = 400

ATTR_INTEGRASJON = "integrasjon"
ATTR_TYPE = "ki_type"

FARGER = ["var(--green)", "var(--blue)", "var(--yellow)", "var(--orange)", "var(--red)", "var(--active-big)"]
