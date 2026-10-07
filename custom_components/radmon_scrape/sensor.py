"""Sensors for Radmon."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import RadmonConfigEntry, RadmonCoordinator
from .entity import RadmonEntity

# Same unit string as 1.x so long-term statistics carry over without a unit-change repair.
UNIT_CPM = "cpm"
UNIT_USV_H = "μSv/h"  # Greek mu, as Home Assistant uses for micro


@dataclass(frozen=True, kw_only=True)
class RadmonSensorDescription(SensorEntityDescription):
    """Describes a Radmon sensor."""

    value_fn: Callable[[RadmonCoordinator], Any]


SENSORS: tuple[RadmonSensorDescription, ...] = (
    RadmonSensorDescription(
        key="cpm",
        translation_key="cpm",
        native_unit_of_measurement=UNIT_CPM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda c: c.data.cpm,
    ),
    RadmonSensorDescription(
        key="usv_ph",
        translation_key="dose_rate",
        native_unit_of_measurement=UNIT_USV_H,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda c: c.data.usv,
    ),
    RadmonSensorDescription(
        key="last_reading",
        translation_key="last_reading",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.data.reading_time,
    ),
    RadmonSensorDescription(
        key="consecutive_errors",
        translation_key="consecutive_errors",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.consecutive_errors,
    ),
    RadmonSensorDescription(
        key="last_update_status",
        translation_key="last_update_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.last_update_status,
    ),
    RadmonSensorDescription(
        key="last_update_time",
        translation_key="last_update_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.last_update_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RadmonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        RadmonSensor(coordinator, description) for description in SENSORS
    )


class RadmonSensor(RadmonEntity, SensorEntity):
    """A Radmon sensor."""

    entity_description: RadmonSensorDescription

    def __init__(
        self, coordinator: RadmonCoordinator, description: RadmonSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Location on the CPM sensor (shows on the map), source on the dose rate."""
        data = self.coordinator.data
        key = self.entity_description.key
        if key == "cpm":
            attrs: dict[str, Any] = {
                "station": self.coordinator.station,
                "mode": self.coordinator.mode,
            }
            if data.location:
                attrs["location"] = data.location
            if data.latitude is not None and data.longitude is not None:
                attrs["latitude"] = data.latitude
                attrs["longitude"] = data.longitude
            if data.device:
                attrs["device"] = data.device
            return attrs
        if key == "usv_ph":
            attrs = {"source": data.usv_source}
            if data.usv_source == "derived":
                attrs["conversion_factor"] = self.coordinator.conversion_factor
            return attrs
        return None
