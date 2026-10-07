"""Constants for the Radmon integration."""

from __future__ import annotations

DOMAIN = "radmon_scrape"
NAME = "Radmon"
VERSION = "2.0.0"
MANUFACTURER = "radmon.org"

BASE_URL = "https://radmon.org"
API_URL = f"{BASE_URL}/radmon.php"
STATION_PAGE_URL = (
    f"{BASE_URL}/index.php?option=com_content&view=article&id=30&station={{station}}"
)
USER_AGENT = (
    f"HomeAssistant-Radmon/{VERSION} (+https://github.com/DonTranQuiL/HA-Radmon)"
)

CONF_STATION = "station"
CONF_PASSWORD = "password"
CONF_MODE = "mode"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CONVERSION_FACTOR = "conversion_factor"
CONF_ALERT_THRESHOLD = "alert_threshold"
CONF_STALE_MINUTES = "stale_minutes"

# Config entry v1 (the old scraper) stored only this key.
LEGACY_CONF_STATION_NAME = "station_name"

MODE_OWNER = "owner"
MODE_PUBLIC = "public"

# Polling. Owner mode uses the two tiny lastreading calls; public mode reads
# the station page, which radmon.org asks people not to hammer.
DEFAULT_SCAN_INTERVAL = {MODE_OWNER: 5, MODE_PUBLIC: 30}
MIN_SCAN_INTERVAL = {MODE_OWNER: 1, MODE_PUBLIC: 15}
MAX_SCAN_INTERVAL = 240

# Common factor for an SBM-20 Geiger-Mueller tube (uSv/h per CPM).
DEFAULT_CONVERSION_FACTOR = 0.0057
DEFAULT_ALERT_THRESHOLD = 100
DEFAULT_STALE_MINUTES = 30

# Station metadata (coordinates, tube) changes rarely.
METADATA_REFRESH_HOURS = 24

PLATFORMS = ["sensor", "binary_sensor"]
