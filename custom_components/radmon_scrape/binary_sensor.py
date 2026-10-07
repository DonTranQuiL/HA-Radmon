"""Binary sensors for Radmon."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALERT_THRESHOLD,
    CONF_STALE_MINUTES,
    DEFAULT_ALERT_THRESHOLD,
    DEFAULT_STALE_MINUTES,
)
from .coordinator import RadmonConfigEntry, RadmonCoordinator
from .entity import RadmonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RadmonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [RadmonOnlineSensor(coordinator), RadmonAlertSensor(coordinator)]
    )


class RadmonOnlineSensor(RadmonEntity, BinarySensorEntity):
    """On while the station keeps reporting."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: RadmonCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "online")

    @property
    def _stale_after(self) -> timedelta:
        return timedelta(
            minutes=self.coordinator.config_entry.options.get(
                CONF_STALE_MINUTES, DEFAULT_STALE_MINUTES
            )
        )

    @property
    def is_on(self) -> bool:
        """True when the last reading is recent."""
        return (
            dt_util.utcnow() - self.coordinator.data.reading_time <= self._stale_after
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Age of the last reading."""
        age = dt_util.utcnow() - self.coordinator.data.reading_time
        return {
            "reading_age_minutes": round(age.total_seconds() / 60, 1),
            "stale_after_minutes": self._stale_after.total_seconds() / 60,
        }


class RadmonAlertSensor(RadmonEntity, BinarySensorEntity):
    """On when CPM reaches the configured alert threshold."""

    _attr_translation_key = "alert"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: RadmonCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "alert")

    @property
    def threshold(self) -> float:
        """Alert level in CPM."""
        return float(
            self.coordinator.config_entry.options.get(
                CONF_ALERT_THRESHOLD, DEFAULT_ALERT_THRESHOLD
            )
        )

    @property
    def is_on(self) -> bool:
        """True at or above the threshold."""
        return self.coordinator.data.cpm >= self.threshold

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The threshold in use."""
        return {"threshold_cpm": self.threshold, "cpm": self.coordinator.data.cpm}
