"""Parser tests (no network)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.radmon_scrape.api import (
    RadmonAuthError,
    RadmonParseError,
    RadmonStationNotFound,
    parse_last_reading,
    parse_station_page,
)

from .conftest import page_html


def test_parse_lastreading_documented_example():
    reading = parse_last_reading(
        "18 CPM on 2022-12-03 17:49:31UTC at Blackpool, Lancashire, United Kingdom"
    )
    assert reading.value == 18
    assert reading.unit == "CPM"
    assert reading.time == datetime(2022, 12, 3, 17, 49, 31, tzinfo=UTC)
    assert reading.location == "Blackpool, Lancashire, United Kingdom"


def test_parse_lastreadingusv_documented_example():
    reading = parse_last_reading(
        "0.225 uSv/hr on 2022-12-03 17:45:31UTC at Blackpool, Lancashire, United Kingdom<br>"
    )
    assert reading.value == pytest.approx(0.225)
    assert reading.unit == "uSv/h"
    assert reading.location == "Blackpool, Lancashire, United Kingdom"


def test_parse_lastreading_without_location_and_decimals():
    reading = parse_last_reading("21.6 CPM on 2026-10-07 15:00:20 UTC")
    assert reading.value == pytest.approx(21.6)
    assert reading.location is None


@pytest.mark.parametrize(
    "text",
    [
        "Fatal error in RadMon : No password specified<br>",
        "Incorrect.<br>",
        "  incorrect. ",
    ],
)
def test_parse_lastreading_auth_errors(text):
    with pytest.raises(RadmonAuthError):
        parse_last_reading(text)


def test_parse_lastreading_garbage():
    with pytest.raises(RadmonParseError):
        parse_last_reading("<html>maintenance</html>")


def test_parse_station_page_real_html():
    page = parse_station_page(page_html())
    assert page.cpm == 30
    assert page.time == datetime(2026, 10, 7, 15, 5, 26, tzinfo=UTC)
    assert page.location == "Aachen, NRW, Germany"
    assert page.latitude == pytest.approx(50.7807)
    assert page.longitude == pytest.approx(6.15)
    assert page.device == "RadMon Plus with SBM-20 tube"


def test_parse_station_page_unknown_station():
    with pytest.raises(RadmonStationNotFound):
        parse_station_page(page_html("station_page_empty.html"))


def test_parse_station_page_garbage():
    with pytest.raises(RadmonParseError):
        parse_station_page("<html><body>Server is too busy</body></html>")


def test_parse_station_page_without_coordinates():
    html = (
        '<h3 class="serif">Somewhere &amp; else<br>\n</h3>'
        '<h2 class="serif">12 CPM on 2026-01-01 00:00:00</h2>'
    )
    page = parse_station_page(html)
    assert page.cpm == 12
    assert page.location == "Somewhere & else"
    assert page.latitude is None
    assert page.device is None
