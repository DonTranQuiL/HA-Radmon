"""Base entity for Radmon."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME, STATION_PAGE_URL, VERSION
from .coordinator import RadmonCoordinator


class RadmonEntity(CoordinatorEntity[RadmonCoordinator]):
    """An entity that belongs to one station device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RadmonCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        station = coordinator.station
        # Same unique ID scheme as 1.x, so existing entities and history are kept.
        self._attr_unique_id = f"{DOMAIN}_{station}_{key}".lower()
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, station.lower())},
            name=f"{NAME} {station}",
            manufacturer=MANUFACTURER,
            model=(
                data.device if data and data.device else "Radiation monitoring station"
            ),
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=STATION_PAGE_URL.format(station=station),
        )
