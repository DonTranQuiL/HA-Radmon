"""The Radmon integration: radiation readings from radmon.org stations."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant

from .const import (
    CONF_MODE,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DEFAULT_SCAN_INTERVAL,
    LEGACY_CONF_STATION_NAME,
    MODE_PUBLIC,
    PLATFORMS,
)
from .coordinator import RadmonConfigEntry, RadmonCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: RadmonConfigEntry) -> bool:
    """Set up a Radmon station from a config entry."""
    coordinator = RadmonCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: RadmonConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RadmonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: RadmonConfigEntry) -> bool:
    """Migrate entries from the 1.x scraper (data: station_name only)."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        station = entry.data.get(LEGACY_CONF_STATION_NAME) or entry.data.get(
            CONF_STATION
        )
        if not station:
            _LOGGER.error(
                "Cannot migrate Radmon entry %s: no station name", entry.entry_id
            )
            return False
        options = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL[MODE_PUBLIC],
            **entry.options,
        }
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_STATION: station, CONF_MODE: MODE_PUBLIC},
            options=options,
            version=2,
        )
        _LOGGER.info("Migrated Radmon station %s to config entry version 2", station)
    return True
