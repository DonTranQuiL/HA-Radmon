# Changelog

## 2.0.0 (unreleased)

A full rewrite. The 1.x code scraped the radmon.org Joomla station page and lived in a
folder (`custom_components/ha-radmon`) whose name didn't match its domain (`radmon_scrape`),
and it depended on page markup that has since changed.

### New
- **Two modes**
  - **Owner mode**: for your own station. Uses radmon.org's official `lastreading` /
    `lastreadingusv` API with the station's data-sending password (radmon.org requires the
    password since May 2026). Gives the station's own µSv/h value.
  - **Public mode**: for any station. Reads the lightweight public station page
    (`showuserpage`) every 30 minutes by default (minimum 15) and calculates µSv/h from CPM.
- Config flow that validates the station (and password) against radmon.org, plus reauth and
  reconfigure flows.
- Options: update interval, CPM→µSv/h conversion factor, alert threshold, offline-after minutes.
- New entities: **Last reading** (timestamp), **Online** (connectivity) and **Radiation alert**
  (safety) binary sensors. Location, coordinates and the counter model are exposed as
  attributes and on the device.
- English and Dutch translations, `icons.json`, diagnostics download (password redacted), brand
  icons.
- Identifying User-Agent and conservative polling, to go easy on radmon.org.
- Full test suite (pytest), hassfest, HACS validation, CodeQL and ruff in CI, and a daily
  watcher that opens an issue if the radmon.org API changes.

### Upgrading from 1.x
- The domain stays `radmon_scrape`, so existing entries are migrated automatically. They become
  **public mode** with a 30-minute interval.
- Unique IDs are unchanged, so your `sensor.radmon_<station>_cpm` and `..._dose_rate` entities,
  history and dashboards keep working.
- The device is now called **Radmon &lt;station&gt;**. Rename it if you prefer the old name.
- To use owner mode, open the entry → ⋮ → **Reconfigure** and enter the data-sending password.
- **Delete the old `custom_components/ha-radmon` folder** after updating. It uses the same domain,
  so if both folders exist Home Assistant may load the old code.
