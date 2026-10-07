"""Diagnostics for Radmon."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, VERSION
from .coordinator import RadmonConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RadmonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "version": VERSION,
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": entry.runtime_data.as_dict(),
    }
