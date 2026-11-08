# Remeha Home integration for Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=home-assistant-community-store&logoColor=white)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hugo-leij&repository=remeha_home&category=integration)
[![Latest release](https://img.shields.io/github/v/release/hugo-leij/remeha_home?label=Release&logo=github)](https://github.com/hugo-leij/remeha_home/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/hugo-leij/remeha_home/remeha_home.zip?label=Downloads&displayAssetName=false&logo=github)](https://github.com/hugo-leij/remeha_home/releases)
[![Tests](https://img.shields.io/github/actions/workflow/status/hugo-leij/remeha_home/tests.yaml?branch=main&label=Tests&logo=github)](https://github.com/hugo-leij/remeha_home/actions/workflows/tests.yaml)
[![Validate](https://img.shields.io/github/actions/workflow/status/hugo-leij/remeha_home/validate.yaml?branch=main&label=Validate&logo=github)](https://github.com/hugo-leij/remeha_home/actions/workflows/validate.yaml)

<p align="center">
  <img src="https://brands.home-assistant.io/remeha_home/logo.png" alt="Remeha Home" width="180">
</p>

This integration lets you control your Remeha Home thermostats from Home Assistant.

This is a fork of [msvisser/remeha_home](https://github.com/msvisser/remeha_home), which is no longer actively maintained.
It adds hot water control, heat pump and cooling support, energy data per heat source, holiday mode and more, collected from community pull requests and tested on a live system.
Please report problems in the [issues of this repository](https://github.com/hugo-leij/remeha_home/issues), and attach the [diagnostics](#diagnostics) if you can.

**Before using this integration, make sure you have set up your thermostat in the [Remeha Home](https://play.google.com/store/apps/details?id=com.bdrthermea.application.remeha) app.**
If you are unable to use the Remeha Home app for your thermostat, this integration will not work.

There have been reports by users that this integration will also work for Baxi, De Dietrich, and Brötje systems (and possibly other BDR Thermea products).
You can simply log in using the credentials that you would use in the respective apps.

## Current features
- All climate zones are exposed as [climate](https://www.home-assistant.io/integrations/climate/) entities with:
    - The following modes:
        - Auto mode: the thermostat will follow the clock program.
        If the target temperature is changed, it will temporarily override the clock program until the next target temperature change in the schedule.
        - Heat mode: the thermostat will be set to manual mode and continuously hold the set temperature.
        For heat pumps this mode is shown as Heat/Cool.
        - Off mode: the thermostat is set to frost protection.
        A temperature can't be set in this mode: change the mode first, or pass `hvac_mode` together with the temperature in `climate.set_temperature`.
    - Three presets for the three clock programs available in the Remeha Home app.
    When a preset is selected, the integration will automatically switch the climate zone to auto mode to make sure the preset is applied.
    In heat (or heat/cool) mode the preset shows Manual, in off mode Frost protection.
- Each climate zone also exposes the following sensors/switches/numbers:
    - The room temperature
    - The status (e.g. heating or idle), plus a binary status sensor (disabled by default)
    - Pre-heat (binary sensor, if reported by the appliance): on while the zone starts heating early to reach the next setpoint of the clock program on time
    - The next schedule setpoint
    - The time at which the next schedule setpoint gets activated
    - The current schedule setpoint
    - The end time of a temporary override (unknown when there is none), also as the `override_end_time` attribute of the climate entity
    - Switch to control fireplace mode
    - The heating curve slope and base setpoint (if supported by the appliance), and its maximum flow temperature (diagnostic).
    They are updated every 15 minutes, so changes made in the Remeha Home app show up.
    - The temperatures of the heating activities used in the clock programs
- Each hot water zone exposes:
    - The water temperature. Combi boilers that don't report it get no water temperature sensor.
    - The current activity (Comfort or Eco)
    - The status, plus a binary status sensor (both disabled by default)
    - The time at which the next schedule setpoint gets activated, and the next activity of the clock program (Comfort or Eco). The API also reports both when the zone doesn't follow the clock program, e.g. in Eco mode.
    - The number of the active hot water clock program (diagnostic), shown with the names of the presets of the climate entity (Schedule 1 to 3)
    - Whether hot water optimization is enabled (binary sensor, diagnostic, if supported by the appliance)
    - Water heater control with modes (Schedule, Comfort, Eco) and target temperature, the same modes as in the Remeha Home app.
    The target temperature is the setpoint of the active activity, Comfort or Eco.
    - Setpoint numbers for the Comfort and Eco temperatures. The Eco temperature is only available for a hot water tank: a combi boiler doesn't keep water warm in Eco, so Remeha has no Eco temperature for it.
    - A Boost switch to start and stop boost (if supported by the appliance). Remeha only accepts boost while the zone is in Schedule mode, so the switch gives an error in other modes. Stopping boost returns the zone to Schedule. While boosting, the water heater shows the Boost mode and its `remaining_boost_time` attribute shows how long it still runs.
- Each appliance (boiler or heat pump) exposes the following sensors:
    - The water pressure, and a Water Pressure problem sensor that turns on when Remeha reports that the pressure is not OK
    - Whether the appliance is online (diagnostic)
    - The thermal mode (e.g. heating, cooling or idle)
    - The operating mode (e.g. AutomaticHeating): what the appliance is set to do, where the thermal mode shows what it is doing now
    - The error status reported by Remeha (e.g. Running)
    - The outdoor temperature measured by the appliance, and the outdoor temperature from the Remeha cloud (disabled by default)
    - Holiday mode (binary sensor), with the scheduled `start_date` and `end_date` as attributes, and actions to schedule and cancel a holiday. After a holiday, the integration sets the zones back to their modes. See [Holiday mode](#holiday-mode).
    - The energy consumed and delivered today for heating, hot water and cooling, for the appliance as a whole (disabled by default)
- Each producer (heat source) of an appliance, such as the heat pump and the gas boiler of a hybrid system, is a separate device with:
    - For heat pumps (and other electric producers): the energy consumed and delivered today for heating, hot water and cooling, and the seasonal efficiency
    - For gas boilers: the gas used today for heating and hot water, in m³

    If the heat pump and gas boiler of a hybrid report the same instance number,
    the gas boiler gets a separate device. Existing IDs are kept when possible;
    check sensor names, units and history after updating.

    The energy values come from Remeha and are updated every 15 minutes. Remeha only reports them with a delay of about 2 hours, and right after midnight the values of the new day start at 0.
    On hybrid setups where the existing gas boiler heats the hot water, such as the Remeha Elga Ace, Remeha does not report the gas used for hot water, so that sensor stays at 0.
    Most of that gas is missing from the Remeha data, and some of it may show up as gas for heating.

    On a hybrid system, the energy consumed by the appliance as a whole is the electricity of the heat pump plus the gas of the gas boiler, both in kWh.
    For the [Energy dashboard](https://www.home-assistant.io/docs/energy/), use the sensors of the producers instead: the heat pump's energy consumed as electricity, and the gas boiler's gas in m³ as gas.

### Read-only energy history

The read-only `remeha_home.get_energy_history` action retrieves Remeha's daily
**space-heating** energy estimates for up to 366 inclusive local calendar days.
Choose a Remeha appliance or producer in **Developer tools → Actions**:

```yaml
action: remeha_home.get_energy_history
data:
  device_id: "<select your Remeha device in the visual editor>"
  start_date: "2026-01-01"
  end_date: "2026-01-31"
```

The response contains daily heat-pump electricity and delivered heat in kWh,
daily indicative heating COP, gas heating energy in kWh, and an energy-weighted
COP over reported days. A flag indicates whether the requested period is
complete. The API's gas kWh differ from the m³ shown by the existing gas
sensors. Remeha's figures are **estimates**, not independently metered
values. No entities or Home Assistant statistics are changed.

## Installation
This integration needs Home Assistant 2026.10 or newer.

### Install with HACS (recommended)
This fork is not in the default list of [HACS](https://hacs.xyz/), so you add it as a custom repository.
Click the button, or follow the steps below.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hugo-leij&repository=remeha_home&category=integration)

1. In HACS, open the menu (⋮) and choose **Custom repositories**
1. Add `https://github.com/hugo-leij/remeha_home` with type **Integration**
1. Search for **Remeha Home**, open it and click **Download**
1. Restart Home Assistant
1. See [Setup](#setup)

Do you already have the original version (msvisser/remeha_home) installed through HACS?
Remove it in HACS first, then download this version: HACS can't track two repositories for the same integration.

### Install manually
1. Download `remeha_home.zip` from the [latest release](https://github.com/hugo-leij/remeha_home/releases/latest)
1. Create a `custom_components/remeha_home` folder in the folder that contains your `configuration.yaml`, if it doesn't exist yet
1. Extract the zip file into that `remeha_home` folder
1. Restart Home Assistant
1. See [Setup](#setup)

## Setup
1. In Home Assistant click on `Settings`
1. Click on `Devices & Services`
1. Click on `+ Add integration`
1. Search for and select `Remeha Home`
1. Enter your email address and password
1. Click "Next"
1. Enjoy

## Holiday mode
Like in the Remeha Home app, you can schedule a holiday period. During the holiday, the appliance sets the climate zones to frost protection and turns the hot water off.
In Home Assistant the thermostats then show Off with the preset Frost protection, and the water heater shows Eco, the state it uses for hot water that is off.

- The Holiday Mode binary sensor of the appliance is on while a holiday is active. Its `start_date` and `end_date` attributes show the scheduled period, also before it starts.
- The `remeha_home.set_holiday_mode` action schedules a holiday from `start_date` to `end_date`. Remeha keeps whole days only. The end date is the day you come back: the holiday ends at midnight UTC before that day, which is 01:00 in Central European winter time.
- The `remeha_home.cancel_holiday_mode` action stops an active holiday or removes a scheduled one.
- When the holiday is over, the integration sets the zones back to the modes they had before. See [After the holiday](#after-the-holiday).

Both actions target the Holiday Mode sensor. You can run them from **Developer tools → Actions**, or use them in automations and scripts.
After an action, the dates update right away. The sensor itself only turns on or off a few seconds later, once Remeha has passed the change on to the appliance.

### After the holiday
When the holiday is over, the appliance should set the zones back to the modes they had before.
It doesn't always do that right away: on a Remeha Elga Ace, a zone that followed its clock program sometimes stayed in frost protection for a few minutes.
Other appliances were reported to keep the frost protection setpoint of 6 °C, or to leave the hot water off, until the mode was set again.
So the integration sets the modes back itself:

- When a holiday starts, it saves the mode of each climate zone and hot water zone, as they were at the last update before the holiday. The saved modes are kept when Home Assistant restarts during the holiday.
- When the holiday is over, it sets each zone that is still in frost protection, or hot water that is still off, back to its saved mode:
    - a climate zone to its clock program, or to manual with its saved temperature;
    - the hot water to its schedule, or to comfort.
- A climate zone that followed its clock program is set to it once more, also when it already shows the clock program again, because it can still keep the frost protection setpoint.
- A temporary change of the clock program, and a hot water boost, come back as the plain clock program and schedule.
- A zone that is in another mode after the holiday keeps that mode, for example when you changed it yourself.
- It checks the result 15 seconds later, and tries up to three times. If the zones are still not back, it logs a warning.

This works when you cancel the holiday in Home Assistant or in the Remeha Home app, and when the holiday ends by itself.
Home Assistant needs to be running when the holiday starts, because it saves the modes then.
A holiday that ends by itself is over at 01:00 (Central European winter time), so the zones come back at the first update after that, within a minute.

### Example scripts
With these two scripts you can set and cancel a holiday from a dashboard.
Create each one in **Settings → Automations & scenes → Scripts → Create script**, choose **Edit in YAML** in the menu (⋮), and paste the YAML.
Replace `binary_sensor.my_home_holiday_mode` with the entity ID of your Holiday Mode sensor.
If you keep your scripts in `scripts.yaml`, put each script under its own key, such as `set_holiday_mode:`.

Set holiday mode, which asks for the dates:
```yaml
alias: Set holiday mode
icon: mdi:beach
fields:
  start_date:
    name: Departure
    required: true
    selector:
      date:
  end_date:
    name: Return
    required: true
    selector:
      date:
sequence:
  - action: remeha_home.set_holiday_mode
    target:
      entity_id: binary_sensor.my_home_holiday_mode
    data:
      start_date: "{{ start_date }}"
      end_date: "{{ end_date }}"
```

Cancel holiday mode:
```yaml
alias: Cancel holiday mode
icon: mdi:home-import-outline
sequence:
  - action: remeha_home.cancel_holiday_mode
    target:
      entity_id: binary_sensor.my_home_holiday_mode
```

Add both scripts to a dashboard, for example with an Entities card.
Click the name of Set holiday mode (not its Run button) to open a dialog where you pick the dates and run the script.
Cancel holiday mode only needs its Run button.

## Diagnostics
The diagnostics show the data that the integration holds, which helps to find the cause of a problem.
To download them, go to **Settings → Devices & services → Remeha Home**, open the menu (⋮) of the entry and choose **Download diagnostics**.

The file contains the dashboard as the integration holds it, the technical details of each appliance and the activities of each climate zone.
The technical details, the activities and the heating curves are the responses of the API, as in the [API documentation](documentation/api.md).
The dashboard is the API response with three additions:
- The energy consumption of today of each appliance (`consumptionData`), as the sensors use it: the heating and hot water of a gas boiler in m³ (its total stays in kWh), and `null` values of a heat source replaced by 0.
- The heating curve of each climate zone (`heatingCurve`).
- The current activity of each hot water zone (`dhwCurrentActivity`).

Your email address, the login token, the names of your home, zones and activities, and the serial numbers of the hardware are replaced by `**REDACTED**`, so you can attach the file to an issue.

## Tests
The tests use the Home Assistant test tools for custom integrations, with anonymized responses of the Remeha API in `tests/fixtures`.
They run on every pull request. To run them yourself (Python 3.14):
```bash
python3 -m pip install -r requirements_test.txt
python3 -m pytest
```

## API documentation
For information on the Remeha Home API see [API documentation](documentation/api.md).

## Contributing
Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how the integration works, how to set up a development environment, and what a pull request needs.
