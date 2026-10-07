"""Data update coordinator for one Radmon station."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import RadmonAuthError, RadmonClient, RadmonError, StationPage
from .const import (
    CONF_CONVERSION_FACTOR,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DEFAULT_CONVERSION_FACTOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    METADATA_REFRESH_HOURS,
    MODE_OWNER,
    MODE_PUBLIC,
)

_LOGGER = logging.getLogger(__name__)

type RadmonConfigEntry = ConfigEntry[RadmonCoordinator]


@dataclass(slots=True)
class RadmonData:
    """The latest state of a station."""

    cpm: float
    reading_time: datetime
    usv: float | None = None
    usv_source: str | None = None  # "station" (radmon.org) or "derived" (CPM x factor)
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    device: str | None = None


def entry_mode(entry: ConfigEntry) -> str:
    """Return owner or public mode for an entry."""
    if entry.data.get(CONF_MODE) in (MODE_OWNER, MODE_PUBLIC):
        return entry.data[CONF_MODE]
    return MODE_OWNER if entry.data.get(CONF_PASSWORD) else MODE_PUBLIC


class RadmonCoordinator(DataUpdateCoordinator[RadmonData]):
    """Poll one station."""

    config_entry: RadmonConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RadmonConfigEntry) -> None:
        """Initialize the coordinator."""
        self.station: str = entry.data[CONF_STATION]
        self.mode = entry_mode(entry)
        minutes = entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL[self.mode]
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.station}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = RadmonClient(
            async_get_clientsession(hass),
            self.station,
            entry.data.get(CONF_PASSWORD) if self.mode == MODE_OWNER else None,
        )
        self.consecutive_errors = 0
        self.last_update_status = "pending"
        self.last_update_time: datetime | None = None
        self._metadata: StationPage | None = None
        self._metadata_time: datetime | None = None

    @property
    def conversion_factor(self) -> float:
        """uSv/h per CPM used for the derived dose rate."""
        return float(
            self.config_entry.options.get(
                CONF_CONVERSION_FACTOR, DEFAULT_CONVERSION_FACTOR
            )
        )

    def _derive(self, cpm: float) -> float:
        return round(cpm * self.conversion_factor, 4)

    async def _async_metadata(self) -> StationPage | None:
        """Station page for coordinates/tube, at most once a day (owner mode)."""
        now = dt_util.utcnow()
        if self._metadata_time and now - self._metadata_time < timedelta(
            hours=METADATA_REFRESH_HOURS
        ):
            return self._metadata
        self._metadata_time = now
        try:
            self._metadata = await self.client.async_station_page()
        except RadmonError as err:
            _LOGGER.debug("Station page for %s unavailable: %s", self.station, err)
        return self._metadata

    async def _fetch(self) -> RadmonData:
        if self.mode == MODE_PUBLIC:
            page = await self.client.async_station_page()
            self._metadata, self._metadata_time = page, dt_util.utcnow()
            return RadmonData(
                cpm=page.cpm,
                reading_time=page.time,
                usv=self._derive(page.cpm),
                usv_source="derived",
                location=page.location,
                latitude=page.latitude,
                longitude=page.longitude,
                device=page.device,
            )

        cpm = await self.client.async_last_reading()
        data = RadmonData(cpm=cpm.value, reading_time=cpm.time, location=cpm.location)
        try:
            usv = await self.client.async_last_reading(usv=True)
        except RadmonAuthError:
            raise
        except RadmonError as err:
            _LOGGER.debug(
                "lastreadingusv failed for %s, deriving: %s", self.station, err
            )
            data.usv, data.usv_source = self._derive(cpm.value), "derived"
        else:
            data.usv, data.usv_source = usv.value, "station"
        meta = await self._async_metadata()
        if meta:
            data = replace(
                data,
                location=data.location or meta.location,
                latitude=meta.latitude,
                longitude=meta.longitude,
                device=meta.device,
            )
        return data

    async def _async_update_data(self) -> RadmonData:
        """Fetch the latest reading."""
        self.last_update_time = dt_util.utcnow()
        try:
            data = await self._fetch()
        except RadmonAuthError as err:
            self.consecutive_errors += 1
            self.last_update_status = "auth_failed"
            raise ConfigEntryAuthFailed(str(err)) from err
        except RadmonError as err:
            self.consecutive_errors += 1
            self.last_update_status = f"error: {err}"[:250]
            if self.data is not None:
                _LOGGER.warning(
                    "Radmon %s update failed (%s in a row), keeping the last reading: %s",
                    self.station,
                    self.consecutive_errors,
                    err,
                )
                return self.data
            raise UpdateFailed(str(err)) from err
        self.consecutive_errors = 0
        self.last_update_status = "ok"
        return data

    def as_dict(self) -> dict[str, Any]:
        """Return the state for diagnostics."""
        data = self.data
        return {
            "mode": self.mode,
            "update_interval_s": self.update_interval.total_seconds()
            if self.update_interval
            else None,
            "consecutive_errors": self.consecutive_errors,
            "last_update_status": self.last_update_status,
            "last_update_time": self.last_update_time.isoformat()
            if self.last_update_time
            else None,
            "data": None
            if data is None
            else {
                "cpm": data.cpm,
                "usv": data.usv,
                "usv_source": data.usv_source,
                "reading_time": data.reading_time.isoformat(),
                "location": data.location,
                "latitude": data.latitude,
                "longitude": data.longitude,
                "device": data.device,
            },
        }
