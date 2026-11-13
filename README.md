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

## Features
- **Thermostat** per climate zone, with the modes auto (follow the clock program), heat (heat/cool on a zone that can cool) and off, and presets for the three clock programs, Manual and Frost protection.
- **Temporary temperature**: hold another temperature for a while, after which the zone returns to its clock program by itself. See [Temporary temperature](#temporary-temperature).
- **Clock program schedules**: the week schedule of the active heating and hot water program, for dashboards and automations. See [Clock program schedules](#clock-program-schedules).
- **Hot water**: a water heater with the Schedule, Comfort and Eco modes, the Comfort and Eco temperatures, and Boost.
- **Heating curve and activity temperatures**: read and change them, as in the Remeha Home app.
- **Holiday mode**: schedule and cancel a holiday; afterwards the integration sets the zones back to their modes. See [Holiday mode](#holiday-mode).
- **Energy** per heat source, such as the heat pump and the gas boiler of a hybrid system, and an action to look back at earlier days. See [Energy](#energy).
- **Status**: water pressure, online, what the appliance is doing, errors, pre-heat and the outdoor temperature.

All entities and what they show are listed in [Entities](https://github.com/hugo-leij/remeha_home/blob/main/documentation/entities.md).

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

## Guides

### Temporary temperature
Hold another temperature for a while with the `remeha_home.set_temporary_override` action, like the timer in the Remeha Home app. See [Temporary temperature](https://github.com/hugo-leij/remeha_home/blob/main/documentation/temporary-temperature.md).

### Clock program schedules
The Clock program sensors have the week schedule of the active program as an attribute, with an example dashboard card. See [Clock program schedules](https://github.com/hugo-leij/remeha_home/blob/main/documentation/clock-programs.md).

### Holiday mode
Schedule and cancel a holiday, and what happens afterwards, with example scripts for a dashboard. See [Holiday mode](https://github.com/hugo-leij/remeha_home/blob/main/documentation/holiday-mode.md).

### Energy
What the energy sensors show, which ones to use for the Energy dashboard, and the energy history action. See [Energy](https://github.com/hugo-leij/remeha_home/blob/main/documentation/energy.md).

## Diagnostics
The diagnostics show the data that the integration holds, which helps to find the cause of a problem.
To download them, go to **Settings → Devices & services → Remeha Home**, open the menu (⋮) of the entry and choose **Download diagnostics**.

The file contains the dashboard as the integration holds it, the technical details of each appliance and the activities of each climate zone.
The technical details, the activities and the heating curves are the responses of the API, as in the [API documentation](https://github.com/hugo-leij/remeha_home/blob/main/documentation/api.md).
The dashboard is the API response with three additions:
- The energy consumption of today of each appliance (`consumptionData`), as the sensors use it: the heating and hot water of a gas boiler in m³ (its total stays in kWh), and `null` values of a heat source replaced by 0.
- The heating curve of each climate zone (`heatingCurve`).
- The current activity of each hot water zone (`dhwCurrentActivity`).

Your email address, the login token, the names of your home, zones and activities, and the serial numbers of the hardware are replaced by `**REDACTED**`, so you can attach the file to an issue.

## Contributing
Contributions are welcome. See [CONTRIBUTING.md](https://github.com/hugo-leij/remeha_home/blob/main/CONTRIBUTING.md) for how the integration works, how to set up a development environment and run the tests, and what a pull request needs.
For the Remeha Home API, see the [API documentation](https://github.com/hugo-leij/remeha_home/blob/main/documentation/api.md).
