# Radmon.org Scraper Integration for Home Assistant

[![HACS Default][hacs_badge]][hacs]
[![Project Maintenance][maintenance_badge]](https://github.com/Malosaaa/radmon-scrape-ha)

This custom component for Home Assistant allows you to monitor radiation data from any station listed on [Radmon.org](https://radmon.org/). It works by scraping the data directly from the station's page, making it a great solution for accessing this data without an official API.

This integration was created with significant collaboration, testing, and debugging from **TranQuiL (@Malosaaa)**.

IMPORTANT NOTICE!!!
I WILL START REWRITING THE WHOLE CODE AS RIGHT NOW IT DOESNT USE THE PERSISTANT MODE!!
U STILL CAN USE IT BUT ITS UNSTABLE NOW!!!


***


## Community

[![Discord](https://img.shields.io/badge/Discord-join%20community-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/qaHPTTKHae)

Join the DonTranQuiL Discord for support and updates.

## Features

*   ✅ **Easy UI-Based Setup**: Configure entirely through the Home Assistant user interface. No YAML required.
*   ✅ **Supports Station Names**: Simply provide the station's name (e.g., `lImbus`) during setup.
*   ✅ **Calculated Dose Rate**: For stations using an SBM-20 tube, the integration automatically calculates the dose rate in µSv/h from the CPM value.
*   ✅ **Device Grouping**: Creates a single Home Assistant Device for your Radmon station, with all sensors neatly attached to it.
*   ✅ **State Restoration**: Sensors will retain their last known value after a Home Assistant restart, preventing automations from firing with `unknown` states.
*   ✅ **Robust Error Handling**: If an update fails, the integration keeps the last successful data and tracks errors with diagnostic sensors.
*   ✅ **Diagnostic Sensors**: Includes disabled-by-default sensors to monitor the health and status of the integration.

## Installation

### Method 1: HACS (Home Assistant Community Store) - Recommended

1.  Ensure you have [HACS](https://hacs.xyz/) installed.
2.  Go to HACS -> Integrations -> Click the 3-dots menu in the top right -> **Custom Repositories**.
3.  In the "Repository" field, paste this URL: `https://github.com/Malosaaa/HA-Radmon`
4.  For "Category", select **Integration**.
5.  Click **Add**.
6.  The "Radmon.org Scraper" integration will now appear in your HACS integrations list. Click **Install**.
7.  Restart Home Assistant.

### Method 2: Manual Installation

1.  Using the Samba-share, File Editor, or another method, navigate to the `custom_components` directory in your Home Assistant `config` folder.
2.  Create a new folder named `ha-radmon`.
3.  Copy all the files from this repository (`__init__.py`, `manifest.json`, `sensor.py`, etc.) into the new `ha-radmon` folder.
4.  Your final file structure should look like this:
    ```
    config/
    └── custom_components/
        └── ha-radmon/
            ├── __init__.py
            ├── manifest.json
            ├── config_flow.py
            ├── const.py
            ├── sensor.py
            └── api.py
    ```
5.  Restart Home Assistant.

## Configuration

After installing (via HACS or manually) and restarting, you can add your Radmon station.

1.  Navigate to **Settings** -> **Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button in the bottom right.
3.  Search for "**Radmon.org Scraper**" and select it.
4.  You will be prompted for a **Station Name**. This is the name shown on the [Radmon Stations List](https://radmon.org/index.php/stations), for example: `lImbus`.
5.  Enter the name and click **Submit**.
6.  The integration will be set up, creating a new device and its associated sensors.

### Enabling Diagnostic Sensors
By default, the diagnostic sensors are disabled. To enable them:
1.  Go to the integration's device page (**Settings -> Devices & Services -> Radmon.org Scraper**).
2.  Click on the device.
3.  In the "Sensors" card, click on a disabled sensor (e.g., "Last Update Time").
4.  Click the cog icon in the top right of the dialog box and toggle the "Enabled" switch.

## Sensors Provided

The integration creates the following sensors:

| Sensor Name                | Example Entity ID                                | Description                                                 |
| -------------------------- | ------------------------------------------------ | ----------------------------------------------------------- |
| **CPM**                    | `sensor.radmon_limbus_cpm`                         | The current radiation level in Counts Per Minute.           |
| **Dose Rate**              | `sensor.radmon_limbus_dose_rate`                   | The calculated dose rate in µSv/h.                          |
| **Consecutive Update Errors** | `sensor.radmon_limbus_consecutive_update_errors` | (Disabled by default) Counts successive update failures.    |
| **Last Update Status**     | `sensor.radmon_limbus_last_update_status`          | (Disabled by default) Shows "OK" or the last error message. |
| **Last Update Time**       | `sensor.radmon_limbus_last_update_time`            | (Disabled by default) A timestamp of the last update attempt. |

## Acknowledgements

*   This project would not have been possible without the excellent work of the **Radmon.org** community.
*   Special thanks to **TranQuiL (@Malosaaa)** for the original idea, dedicated testing, and collaborative debugging that made this integration robust and feature-complete.

> **Disclaimer:** This integration relies on web scraping. If Radmon.org changes the HTML structure of their station pages, this integration will likely break until it is updated.

[hacs]: https://hacs.xyz
[hacs_badge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[maintenance_badge]: https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge
