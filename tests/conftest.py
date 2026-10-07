"""Shared fixtures for Radmon tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.radmon_scrape.const import (
    API_URL,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DOMAIN,
    MODE_OWNER,
    MODE_PUBLIC,
)

FIXTURES = Path(__file__).parent / "fixtures"
STATION = "lImbus"
PASSWORD = "s3cret"
CPM_TEXT = "18 CPM on 2026-10-07 15:00:20UTC at Aachen, NRW, Germany"
USV_TEXT = "0.103 uSv/hr on 2026-10-07 15:00:20UTC at Aachen, NRW, Germany"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations automatically for all tests."""
    yield


def page_html(name: str = "station_page.html") -> str:
    """Return a saved radmon.org station page."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def mock_page(
    aioclient_mock, station: str = STATION, text: str | None = None, **kwargs
) -> None:
    """Mock the public station page."""
    if "exc" not in kwargs and "status" not in kwargs:
        kwargs["text"] = page_html() if text is None else text
    elif text is not None:
        kwargs["text"] = text
    aioclient_mock.get(
        API_URL, params={"function": "showuserpage", "user": station}, **kwargs
    )


def mock_owner(
    aioclient_mock,
    cpm: str = "18 CPM on 2026-10-07 15:00:20UTC at Aachen, NRW, Germany",
    usv: str | None = "0.103 uSv/hr on 2026-10-07 15:00:20UTC at Aachen, NRW, Germany",
    password: str = PASSWORD,
    **kwargs,
) -> None:
    """Mock the lastreading/lastreadingusv calls."""
    aioclient_mock.get(
        API_URL,
        params={"function": "lastreading", "user": STATION, "password": password},
        text=cpm,
        **kwargs,
    )
    if usv is not None:
        aioclient_mock.get(
            API_URL,
            params={
                "function": "lastreadingusv",
                "user": STATION,
                "password": password,
            },
            text=usv,
        )


@pytest.fixture
def public_entry() -> MockConfigEntry:
    """A public-mode entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Radmon {STATION}",
        unique_id=STATION.lower(),
        version=2,
        data={CONF_STATION: STATION, CONF_MODE: MODE_PUBLIC},
        options={CONF_SCAN_INTERVAL: 30},
    )


@pytest.fixture
def owner_entry() -> MockConfigEntry:
    """An owner-mode entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Radmon {STATION}",
        unique_id=STATION.lower(),
        version=2,
        data={CONF_STATION: STATION, CONF_MODE: MODE_OWNER, CONF_PASSWORD: PASSWORD},
        options={CONF_SCAN_INTERVAL: 5},
    )
