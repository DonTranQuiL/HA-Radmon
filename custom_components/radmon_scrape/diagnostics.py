"""Diagnostics for Radmon."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_STATION, LEGACY_CONF_STATION_NAME, VERSION
from .coordinator import RadmonConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_STATION,
    LEGACY_CONF_STATION_NAME,
    "title",
    "location",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RadmonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "version": VERSION,
            "entry": {
                "title": entry.title,
                "version": entry.version,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "coordinator": entry.runtime_data.as_dict(),
        },
        TO_REDACT,
    )
