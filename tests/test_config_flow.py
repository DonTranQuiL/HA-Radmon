"""Config, reauth, reconfigure and options flow tests."""

from __future__ import annotations

from unittest.mock import patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.radmon_scrape.const import (
    CONF_ALERT_THRESHOLD,
    CONF_CONVERSION_FACTOR,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_STALE_MINUTES,
    CONF_STATION,
    DOMAIN,
    MODE_OWNER,
    MODE_PUBLIC,
)

from .conftest import PASSWORD, STATION, mock_owner, mock_page, page_html


@pytest.fixture(autouse=True)
def no_setup():
    """Don't set the entry up after the flow."""
    with patch("custom_components.radmon_scrape.async_setup_entry", return_value=True):
        yield


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_public_station(hass: HomeAssistant, aioclient_mock) -> None:
    mock_page(aioclient_mock)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION: f"  {STATION} "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Radmon {STATION}"
    assert result["data"] == {CONF_STATION: STATION, CONF_MODE: MODE_PUBLIC}
    assert result["options"] == {CONF_SCAN_INTERVAL: 30}
    assert result["result"].unique_id == STATION.lower()


async def test_owner_station(hass: HomeAssistant, aioclient_mock) -> None:
    mock_owner(aioclient_mock)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION: STATION, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_STATION: STATION,
        CONF_MODE: MODE_OWNER,
        CONF_PASSWORD: PASSWORD,
    }
    assert result["options"] == {CONF_SCAN_INTERVAL: 5}


@pytest.mark.parametrize(
    ("owner", "kwargs", "error"),
    [
        (True, {"text": "Incorrect.<br>"}, "invalid_auth"),
        (True, {"text": "something odd"}, "invalid_response"),
        (False, {"text": page_html("station_page_empty.html")}, "station_not_found"),
        (False, {"exc": aiohttp.ClientError()}, "cannot_connect"),
        (False, {"exc": TimeoutError()}, "cannot_connect"),
        (False, {"status": 500}, "cannot_connect"),
        (False, {"status": 429}, "cannot_connect"),
    ],
)
async def test_errors(
    hass: HomeAssistant, aioclient_mock, owner, kwargs, error
) -> None:
    if owner:
        text = kwargs.pop("text")
        mock_owner(aioclient_mock, cpm=text, usv=None, **kwargs)
        user_input = {CONF_STATION: STATION, CONF_PASSWORD: PASSWORD}
    else:
        mock_page(aioclient_mock, **kwargs)
        user_input = {CONF_STATION: STATION}
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_unexpected_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(
        "custom_components.radmon_scrape.config_flow.validate_station",
        side_effect=ValueError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_STATION: STATION}
        )
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured(
    hass: HomeAssistant, aioclient_mock, public_entry
) -> None:
    public_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION: STATION.upper()}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, aioclient_mock, owner_entry) -> None:
    owner_entry.add_to_hass(hass)
    mock_owner(aioclient_mock, password="new-pass")
    result = await owner_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-pass"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert owner_entry.data[CONF_PASSWORD] == "new-pass"


async def test_reauth_wrong_password(
    hass: HomeAssistant, aioclient_mock, owner_entry
) -> None:
    owner_entry.add_to_hass(hass)
    mock_owner(aioclient_mock, cpm="Incorrect.<br>", usv=None, password="bad")
    result = await owner_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_owner_to_public(
    hass: HomeAssistant, aioclient_mock, owner_entry
) -> None:
    owner_entry.add_to_hass(hass)
    mock_page(aioclient_mock)
    result = await owner_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert owner_entry.data == {CONF_STATION: STATION, CONF_MODE: MODE_PUBLIC}
    assert owner_entry.options[CONF_SCAN_INTERVAL] == 30


async def test_reconfigure_public_to_owner(
    hass: HomeAssistant, aioclient_mock, public_entry
) -> None:
    public_entry.add_to_hass(hass)
    mock_owner(aioclient_mock)
    result = await public_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD}
    )
    assert result["reason"] == "reconfigure_successful"
    assert public_entry.data[CONF_MODE] == MODE_OWNER
    assert public_entry.options[CONF_SCAN_INTERVAL] == 5


async def test_options(hass: HomeAssistant, public_entry) -> None:
    public_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(public_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["min_interval"] == "15"
    new = {
        CONF_SCAN_INTERVAL: 45,
        CONF_CONVERSION_FACTOR: 0.0065,
        CONF_ALERT_THRESHOLD: 80,
        CONF_STALE_MINUTES: 60,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], new)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert public_entry.options == new
