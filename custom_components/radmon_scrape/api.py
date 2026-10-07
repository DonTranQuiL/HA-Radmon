"""Client for the radmon.org station data.

Two documented sources are used (https://radmon.org, see the User API
specification and the forum note of 24 May 2026):

* ``radmon.php?function=lastreading`` / ``lastreadingusv`` with ``user`` and the
  station's *data-sending password* (owner mode). Returns for example
  ``18 CPM on 2022-12-03 17:49:31UTC at Blackpool, Lancashire, United Kingdom``.
* ``radmon.php?function=showuserpage&user=...``: the small public station page
  with the last CPM reading, location, coordinates and tube (public mode, and
  for station metadata).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import aiohttp

from .const import API_URL, USER_AGENT

TIMEOUT = aiohttp.ClientTimeout(total=20)

_NUMBER = r"-?\d+(?:\.\d+)?"
_STAMP = r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"
LAST_READING_RE = re.compile(
    rf"^\s*(?P<value>{_NUMBER})\s*(?P<unit>CPM|uSv/hr?)\s+on\s+(?P<stamp>{_STAMP})\s*(?:UTC)?"
    r"(?:\s+at\s+(?P<location>.*?))?\s*(?:<br\s*/?>)?\s*$",
    re.IGNORECASE | re.DOTALL,
)
PAGE_READING_RE = re.compile(
    rf'<h2 class="serif">\s*(?P<value>{_NUMBER})\s*CPM\s+on\s+(?P<stamp>{_STAMP})\s*</h2>',
    re.IGNORECASE,
)
PAGE_EMPTY_RE = re.compile(r'<h2 class="serif">\s*CPM\s+on\s*</h2>', re.IGNORECASE)
PAGE_DETAILS_RE = re.compile(
    r'<h3 class="serif">(?P<body>.*?)</h3>', re.IGNORECASE | re.DOTALL
)
COORDS_RE = re.compile(
    rf"^(?P<location>.*?)\s*at coordinates\s*(?P<lat>{_NUMBER})?\s*,\s*(?P<lon>{_NUMBER})?\s*$",
    re.IGNORECASE | re.DOTALL,
)
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")


class RadmonError(Exception):
    """Base error."""


class RadmonConnectionError(RadmonError):
    """radmon.org could not be reached."""


class RadmonAuthError(RadmonError):
    """The station name or data-sending password was rejected."""


class RadmonStationNotFound(RadmonError):
    """The station page has no readings (unknown or never-reporting station)."""


class RadmonParseError(RadmonError):
    """The response did not have the documented format."""


@dataclass(slots=True)
class LastReading:
    """A parsed lastreading/lastreadingusv response."""

    value: float
    unit: str
    time: datetime
    location: str | None


@dataclass(slots=True)
class StationPage:
    """The parsed public station page."""

    cpm: float
    time: datetime
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    device: str | None = None


def _utc(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("T", " ")).replace(tzinfo=UTC)


def _clean(text: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub("", text)).split())


def parse_last_reading(text: str) -> LastReading:
    """Parse a lastreading or lastreadingusv response."""
    lowered = text.lower()
    if "no password" in lowered or lowered.strip().startswith("incorrect"):
        raise RadmonAuthError(_clean(text) or "rejected")
    match = LAST_READING_RE.match(text)
    if not match:
        raise RadmonParseError(f"Unexpected response: {_clean(text)[:120]!r}")
    location = match.group("location")
    return LastReading(
        value=float(match.group("value")),
        unit="CPM" if match.group("unit").upper() == "CPM" else "uSv/h",
        time=_utc(match.group("stamp")),
        location=_clean(location) if location else None,
    )


def parse_station_page(page: str) -> StationPage:
    """Parse the public showuserpage HTML."""
    match = PAGE_READING_RE.search(page)
    if not match:
        if PAGE_EMPTY_RE.search(page):
            raise RadmonStationNotFound("The station has no readings")
        raise RadmonParseError("Could not find the reading on the station page")
    result = StationPage(
        cpm=float(match.group("value")), time=_utc(match.group("stamp"))
    )
    details = PAGE_DETAILS_RE.search(page)
    if details:
        parts = [_clean(p) for p in BR_RE.split(details.group("body"))]
        parts = [p for p in parts if p]
        if parts:
            coords = COORDS_RE.match(parts[0])
            if coords:
                result.location = coords.group("location") or None
                if coords.group("lat") and coords.group("lon"):
                    result.latitude = float(coords.group("lat"))
                    result.longitude = float(coords.group("lon"))
            else:
                result.location = parts[0]
        if len(parts) > 1:
            result.device = parts[1]
    return result


class RadmonClient:
    """Small async client for one station."""

    def __init__(
        self, session: aiohttp.ClientSession, station: str, password: str | None = None
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.station = station
        self._password = password or None

    @property
    def is_owner(self) -> bool:
        """True when the data-sending password is configured."""
        return self._password is not None

    async def _get(self, params: dict[str, str]) -> str:
        try:
            async with self._session.get(
                API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            ) as response:
                if response.status == 429:
                    raise RadmonConnectionError(
                        "radmon.org is rate limiting (HTTP 429)"
                    )
                response.raise_for_status()
                return await response.text()
        except TimeoutError as err:
            raise RadmonConnectionError("Timed out talking to radmon.org") from err
        except aiohttp.ClientError as err:
            raise RadmonConnectionError(f"Error talking to radmon.org: {err}") from err

    async def async_last_reading(self, usv: bool = False) -> LastReading:
        """Return the station's last reading (owner mode)."""
        if not self._password:
            raise RadmonAuthError("No data-sending password configured")
        text = await self._get(
            {
                "function": "lastreadingusv" if usv else "lastreading",
                "user": self.station,
                "password": self._password,
            }
        )
        return parse_last_reading(text)

    async def async_station_page(self) -> StationPage:
        """Return the parsed public station page."""
        text = await self._get({"function": "showuserpage", "user": self.station})
        return parse_station_page(text)
