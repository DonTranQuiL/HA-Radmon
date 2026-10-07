"""Setup, entities, coordinator, migration and diagnostics tests."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.radmon_scrape import const
from custom_components.radmon_scrape.const import (
    CONF_ALERT_THRESHOLD,
    CONF_CONVERSION_FACTOR,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_STATION,
    DOMAIN,
    MODE_PUBLIC,
)
from custom_components.radmon_scrape.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import PASSWORD, STATION, mock_owner, mock_page

ROOT = Path(__file__).parent.parent
PREFIX = "radmon_limbus"
FROZEN = "2026-10-07 15:10:00+00:00"


def test_version_matches_manifest():
    manifest = json.loads(
        (ROOT / "custom_components/radmon_scrape/manifest.json").read_text()
    )
    assert manifest["version"] == const.VERSION
    assert manifest["domain"] == const.DOMAIN
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert "domains" not in hacs


def test_translations_in_sync():
    base = ROOT / "custom_components/radmon_scrape/translations"
    en, nl = (json.loads((base / f"{lang}.json").read_text()) for lang in ("en", "nl"))

    def keys(data, prefix=""):
        out = set()
        for key, value in data.items():
            out |= (
                keys(value, f"{prefix}{key}.")
                if isinstance(value, dict)
                else {prefix + key}
            )
        return out

    assert keys(en) == keys(nl)


def test_brand_images_present():
    brand = ROOT / "custom_components/radmon_scrape/brand"
    for name in (
        "icon.png",
        "icon@2x.png",
        "logo.png",
        "logo@2x.png",
        "dark_icon.png",
        "dark_icon@2x.png",
        "dark_logo.png",
        "dark_logo@2x.png",
    ):
        assert (brand / name).is_file(), name


@pytest.mark.freeze_time(FROZEN)
async def test_public_setup(hass: HomeAssistant, aioclient_mock, public_entry) -> None:
    mock_page(aioclient_mock)
    public_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(public_entry.entry_id)
    await hass.async_block_till_done()
    assert public_entry.state is ConfigEntryState.LOADED

    cpm = hass.states.get(f"sensor.{PREFIX}_cpm")
    assert cpm.state == "30.0"
    assert cpm.attributes["unit_of_measurement"] == "cpm"
    assert cpm.attributes["state_class"] == "measurement"
    assert cpm.attributes["latitude"] == pytest.approx(50.7807)
    assert cpm.attributes["device"] == "RadMon Plus with SBM-20 tube"

    dose = hass.states.get(f"sensor.{PREFIX}_dose_rate")
    assert float(dose.state) == pytest.approx(30 * 0.0057, abs=1e-4)
    assert dose.attributes["source"] == "derived"
    assert dose.attributes["unit_of_measurement"] == "μSv/h"

    assert (
        hass.states.get(f"sensor.{PREFIX}_last_reading").state
        == "2026-10-07T15:05:26+00:00"
    )
    assert hass.states.get(f"binary_sensor.{PREFIX}_online").state == "on"
    alert = hass.states.get(f"binary_sensor.{PREFIX}_radiation_alert")
    assert alert.state == "off"
    assert alert.attributes["threshold_cpm"] == 100

    ent_reg = er.async_get(hass)
    assert (
        ent_reg.async_get(f"sensor.{PREFIX}_cpm").unique_id
        == "radmon_scrape_limbus_cpm"
    )
    assert (
        ent_reg.async_get(f"sensor.{PREFIX}_dose_rate").unique_id
        == "radmon_scrape_limbus_usv_ph"
    )
    diag = ent_reg.async_get(f"sensor.{PREFIX}_last_update_status")
    assert diag.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert diag.entity_category == "diagnostic"

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "limbus")})
    assert device.name == "Radmon lImbus"
    assert device.model == "RadMon Plus with SBM-20 tube"
    assert (
        len(
            er.async_entries_for_device(
                ent_reg, device.id, include_disabled_entities=True
            )
        )
        == 8
    )

    assert await hass.config_entries.async_unload(public_entry.entry_id)
    assert public_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.freeze_time(FROZEN)
async def test_owner_setup_uses_station_dose(
    hass: HomeAssistant, aioclient_mock, owner_entry
) -> None:
    mock_owner(aioclient_mock)
    mock_page(aioclient_mock)
    owner_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(owner_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(f"sensor.{PREFIX}_cpm").state == "18.0"
    dose = hass.states.get(f"sensor.{PREFIX}_dose_rate")
    assert dose.state == "0.103"
    assert dose.attributes["source"] == "station"
    cpm = hass.states.get(f"sensor.{PREFIX}_cpm")
    assert cpm.attributes["location"] == "Aachen, NRW, Germany"
    assert cpm.attributes["longitude"] == pytest.approx(6.15)


@pytest.mark.freeze_time(FROZEN)
async def test_owner_usv_failure_derives(
    hass: HomeAssistant, aioclient_mock, owner_entry
) -> None:
    mock_owner(aioclient_mock, usv="weird")
    mock_page(aioclient_mock, status=500)
    owner_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        owner_entry, options={CONF_CONVERSION_FACTOR: 0.01}
    )
    assert await hass.config_entries.async_setup(owner_entry.entry_id)
    await hass.async_block_till_done()
    dose = hass.states.get(f"sensor.{PREFIX}_dose_rate")
    assert float(dose.state) == pytest.approx(0.18)
    assert dose.attributes == dose.attributes | {
        "source": "derived",
        "conversion_factor": 0.01,
    }
    assert "latitude" not in hass.states.get(f"sensor.{PREFIX}_cpm").attributes


async def test_owner_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock, owner_entry
) -> None:
    mock_owner(aioclient_mock, cpm="Incorrect.<br>", usv=None)
    owner_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(owner_entry.entry_id)
    await hass.async_block_till_done()
    assert owner_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == SOURCE_REAUTH for f in flows)


async def test_setup_retry_when_down(
    hass: HomeAssistant, aioclient_mock, public_entry
) -> None:
    mock_page(aioclient_mock, status=503)
    public_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(public_entry.entry_id)
    assert public_entry.state is ConfigEntryState.SETUP_RETRY


async def test_failed_update_keeps_last_reading_and_goes_offline(
    hass: HomeAssistant, aioclient_mock, public_entry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(FROZEN)
    mock_page(aioclient_mock)
    public_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        public_entry, options={CONF_SCAN_INTERVAL: 30, CONF_ALERT_THRESHOLD: 25}
    )
    assert await hass.config_entries.async_setup(public_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(f"binary_sensor.{PREFIX}_radiation_alert").state == "on"

    aioclient_mock.clear_requests()
    mock_page(aioclient_mock, status=500)
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = public_entry.runtime_data
    assert coordinator.consecutive_errors == 1
    assert coordinator.last_update_status.startswith("error")
    assert hass.states.get(f"sensor.{PREFIX}_cpm").state == "30.0"
    assert hass.states.get(f"binary_sensor.{PREFIX}_online").state == "off"


async def test_migrate_v1_entry(hass: HomeAssistant, aioclient_mock) -> None:
    """A 1.x scraper entry becomes a v2 public entry and keeps its entities."""
    mock_page(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Radmon {STATION}",
        unique_id=STATION.lower(),
        version=1,
        data={"station_name": STATION},
    )
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    old = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "radmon_scrape_limbus_cpm",
        config_entry=entry,
        suggested_object_id="radmon_limbus_radmon_limbus_cpm",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert entry.data == {CONF_STATION: STATION, CONF_MODE: MODE_PUBLIC}
    assert entry.options[CONF_SCAN_INTERVAL] == 30
    assert hass.states.get(old.entity_id).state == "30.0"


async def test_migrate_future_version_fails(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={CONF_STATION: STATION})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_without_station_fails(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=1, data={})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_diagnostics_redacts_password(
    hass: HomeAssistant, aioclient_mock, owner_entry
) -> None:
    mock_owner(aioclient_mock)
    mock_page(aioclient_mock)
    owner_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(owner_entry.entry_id)
    await hass.async_block_till_done()
    diag = await async_get_config_entry_diagnostics(hass, owner_entry)
    assert diag["entry"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert PASSWORD not in json.dumps(diag)
    assert diag["coordinator"]["mode"] == "owner"
    assert diag["coordinator"]["data"]["cpm"] == 18
    assert diag["version"] == const.VERSION


async def test_options_change_reloads(
    hass: HomeAssistant, aioclient_mock, public_entry
) -> None:
    mock_page(aioclient_mock)
    public_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(public_entry.entry_id)
    await hass.async_block_till_done()
    hass.config_entries.async_update_entry(
        public_entry, options={CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()
    assert public_entry.runtime_data.update_interval == timedelta(minutes=60)
