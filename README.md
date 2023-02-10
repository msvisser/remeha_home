# Remeha Home integration for Home Assistant
This integration lets you control your Remeha Home thermostats from Home Assistant.

**Before using this integration, make sure you have set up your thermostat in the [Remeha Home](https://play.google.com/store/apps/details?id=com.bdrthermea.application.remeha) app.**
If you are unable to use the Remeha Home app for your thermostat, this integration will not work.

## Current features
- All climate zones are exposed as [climate](https://www.home-assistant.io/integrations/climate/) entities with:
    - The following modes:
        - Auto mode: the thermostat will follow the clock program.
        If the target temperature is changed, it will temporarily override the clock program until the next target temperature change in the schedule.
        - Heat mode: the thermostat will be set to manual mode and continuously hold the set temperature.
        - Off mode: the thermostat is disabled.
    - Three presets for the three clock programs available in the Remeha Home app.
- Each climate zone exposes the following sensors:
    - The next schedule setpoint
    - The time at which the next schedule setpoint gets activated
    - The current schedule setpoint
- Each appliance (CV-ketel) exposes the following sensors:
    - The water pressure

## Installation

### Install with HACS (recommended)

Do you have [HACS](https://hacs.xyz/) installed?
1. Add a custom repository to HACS: `msvisser/remeha_home` of type `Integration`
1. Search integrations for **Remeha Home**
1. Click `Install`
1. Restart Home Assistant
1. See [Setup](#setup)

### Install manually

1. Install this platform by creating a `custom_components` folder in the same folder as your configuration.yaml, if it doesn't already exist.
2. Create another folder `remeha_home` in the `custom_components` folder. Copy all files from `custom_components/remeha_home` into the `remeha_home` folder.

## Setup
1. In Home Assitant click on `Configuration`
1. Click on `Integrations`
1. Click on `+ Add integration`
1. Search for and select `Remeha Home`
1. Enter your email address and password
1. Click "Next"
1. Enjoy
