"""Diagnostica."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import OfferteConfigEntry
from .const import CONF_CODICE, CONF_COMUNE

REDACT = {CONF_COMUNE, CONF_CODICE}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: OfferteConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    return {
        "data": async_redact_data(dict(entry.data), REDACT),
        "options": async_redact_data(dict(entry.options), REDACT),
        "risultato": asdict(c.data) if c.data else None,
    }
