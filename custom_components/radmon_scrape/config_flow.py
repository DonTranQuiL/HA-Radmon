"""Config flow for Radmon."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    RadmonAuthError,
    RadmonClient,
    RadmonConnectionError,
    RadmonError,
    RadmonStationNotFound,
)
from .const import (
    BASE_URL,
    CONF_ALERT_THRESHOLD,
    CONF_CONVERSION_FACTOR,
    CONF_MODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_STALE_MINUTES,
    CONF_STATION,
    DEFAULT_ALERT_THRESHOLD,
    DEFAULT_CONVERSION_FACTOR,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MODE_OWNER,
    MODE_PUBLIC,
    NAME,
)
from .coordinator import entry_mode

_LOGGER = logging.getLogger(__name__)

PLACEHOLDERS = {
    "stations_url": f"{BASE_URL}/index.php/stations",
    "radmon_url": BASE_URL,
}
PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


async def validate_station(
    hass: HomeAssistant, station: str, password: str | None
) -> None:
    """Fetch one reading to check the station (and password)."""
    client = RadmonClient(async_get_clientsession(hass), station, password)
    if password:
        await client.async_last_reading()
    else:
        await client.async_station_page()


def _errors_for(err: Exception) -> str:
    if isinstance(err, RadmonAuthError):
        return "invalid_auth"
    if isinstance(err, RadmonStationNotFound):
        return "station_not_found"
    if isinstance(err, RadmonConnectionError):
        return "cannot_connect"
    if isinstance(err, RadmonError):
        return "invalid_response"
    return "unknown"


class RadmonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radmon."""

    VERSION = 2

    async def _async_check(self, station: str, password: str | None) -> dict[str, str]:
        try:
            await validate_station(self.hass, station, password)
        except Exception as err:  # noqa: BLE001 - mapped to a form error
            if not isinstance(err, RadmonError):
                _LOGGER.exception(
                    "Unexpected error validating Radmon station %s", station
                )
            return {"base": _errors_for(err)}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the station name and the optional data-sending password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            station = user_input[CONF_STATION].strip()
            password = (user_input.get(CONF_PASSWORD) or "").strip() or None
            await self.async_set_unique_id(station.lower())
            self._abort_if_unique_id_configured()
            errors = await self._async_check(station, password)
            if not errors:
                mode = MODE_OWNER if password else MODE_PUBLIC
                data = {CONF_STATION: station, CONF_MODE: mode}
                if password:
                    data[CONF_PASSWORD] = password
                return self.async_create_entry(
                    title=f"{NAME} {station}",
                    data=data,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL[mode]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_STATION): str,
                        vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR,
                    }
                ),
                user_input,
            ),
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when radmon.org rejects the password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new data-sending password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            password = user_input[CONF_PASSWORD].strip()
            errors = await self._async_check(entry.data[CONF_STATION], password)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: password, CONF_MODE: MODE_OWNER}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders={
                **PLACEHOLDERS,
                "station": entry.data[CONF_STATION],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add, change or remove the data-sending password (switches mode)."""
        entry = self._get_reconfigure_entry()
        station = entry.data[CONF_STATION]
        errors: dict[str, str] = {}
        if user_input is not None:
            password = (user_input.get(CONF_PASSWORD) or "").strip() or None
            errors = await self._async_check(station, password)
            if not errors:
                mode = MODE_OWNER if password else MODE_PUBLIC
                data = {CONF_STATION: station, CONF_MODE: mode}
                if password:
                    data[CONF_PASSWORD] = password
                options = dict(entry.options)
                if entry_mode(entry) != mode:
                    options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL[mode]
                return self.async_update_reload_and_abort(
                    entry, data=data, options=options
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Optional(CONF_PASSWORD): PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders={**PLACEHOLDERS, "station": station},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RadmonOptionsFlow:
        """Return the options flow."""
        return RadmonOptionsFlow()


class RadmonOptionsFlow(OptionsFlow):
    """Polling, conversion factor and alert options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        mode = entry_mode(self.config_entry)
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL[mode]
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL[mode],
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="min",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_CONVERSION_FACTOR,
                    default=options.get(
                        CONF_CONVERSION_FACTOR, DEFAULT_CONVERSION_FACTOR
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.0001,
                        max=1,
                        step="any",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_ALERT_THRESHOLD,
                    default=options.get(CONF_ALERT_THRESHOLD, DEFAULT_ALERT_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=100000,
                        step=1,
                        unit_of_measurement="cpm",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_STALE_MINUTES,
                    default=options.get(CONF_STALE_MINUTES, DEFAULT_STALE_MINUTES),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=1440,
                        step=1,
                        unit_of_measurement="min",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "mode": mode,
                "min_interval": str(MIN_SCAN_INTERVAL[mode]),
            },
        )
