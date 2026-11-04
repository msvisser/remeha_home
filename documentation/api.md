# Remeha Home API
The Remeha Home app talks to a cloud API of BDR Thermea.
This page describes the parts of that API that this integration uses, and how they behave.

> [!NOTE]
> This information was obtained by sniffing the traffic of the Remeha Home app and by testing against the live API.
> It is not official documentation. Please use it responsibly.

## Contents
- [Basics](#basics): requests, times and errors
- [Dashboard](#dashboard): the state of all appliances and zones
- [Appliances](#appliances): technical details and holiday mode
- [Climate zones](#climate-zones): modes, setpoints, heating curve and activities
- [Hot water zones](#hot-water-zones): modes, boost and setpoints
- [Energy consumption](#energy-consumption): energy per hour, day, month and year

## Basics

### Requests
The API is located at `https://api.bdrthermea.net/Mobile/api/`.
Every request needs a valid OAuth2 token from the BDR B2C OAuth2 API, and these two headers:
```
Authorization: Bearer <token>
Ocp-Apim-Subscription-Key: df605c5470d846fc91e848b1cc653ddf
```

Requests that change something are `POST` requests (one `PUT`), with a JSON body where noted.
A change can take a few seconds to show up in the [dashboard](#dashboard).

### Times
Most times are **local times with a `Z` suffix**: `2026-10-22T22:00:00Z` means 22:00 in the time zone of the appliance, not 22:00 UTC.
Two times are real UTC. This was measured on a live system and checked against the Remeha Home app:

| Field | Format | Measured |
|---|---|---|
| `nextSwitchTime` (climate and hot water zones) | Local time | A schedule switch at 22:00 CEST is `22:00:00Z` |
| `holidaySchedule.startTime` and `endTime` | Date | Whole days, stored as `<date>T00:00:01Z`. A holiday until 27 October ended at 00:00 UTC (01:00 CET), see [holiday mode](#holiday-mode) |
| `temporaryOverride.endTime` | **UTC** | An override until the schedule resumes at 22:00 CEST is `20:00:00Z` |
| `boostModeEndTime` | **UTC** | A 30 minute boost started at 14:41:59 CEST ends at `13:11:59.2692621Z` |

A time in the year 1 means "not set", for example `0001-01-01T00:00:00Z` or `0001-01-01T00:00:01Z`.

The energy consumption endpoints have their own rules, see [Energy consumption](#energy-consumption).

### Errors
A rejected request returns an HTTP error, usually with a problem details body.
The messages are in `errors`:
```json
{
  "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
  "title": "Bad Request",
  "status": 400,
  "errors": {
    "": [
      "Start Date must be before the End Date."
    ]
  },
  "traceId": "00-..."
}
```

## Dashboard

### Get the dashboard
```http
GET /homes/dashboard
```

Returns the state of all appliances with their climate zones and hot water zones, as shown when the app opens.
The integration polls it every minute, with a `?t=<unix time>` query parameter to prevent caching.

The available fields differ per appliance. The most important ones:

| Field | Values and notes |
|---|---|
| **Appliance** | |
| `applianceType` | e.g. `Boiler` or `HeatPump` |
| `applianceOnline` | `true` while the appliance is connected |
| `errorStatus` | e.g. `Running` |
| `operatingMode` | e.g. `AutomaticHeating`: what the appliance is set to do |
| `activeThermalMode` | e.g. `Idle`, `HeatingCH`, `HeatingDHW` or `Cooling`: what the appliance is doing now |
| `waterPressure`, `waterPressureOK` | Pressure in bar, and whether Remeha considers it OK |
| `outdoorTemperatureInformation` | `applianceOutdoorTemperature` from the appliance's sensor, `cloudOutdoorTemperature` from a weather service |
| `holidaySchedule` | `startTime`, `endTime` (dates, year 1 when not set) and `active`, see [holiday mode](#holiday-mode) |
| `gasCalorificValue` | kWh per m³ of gas, to convert the gas energy of the [energy consumption](#energy-consumption) to m³ |
| **Climate zone** | |
| `zoneMode` | `Scheduling`, `TemporaryOverride`, `Manual` or `FrostProtection` |
| `activeComfortDemand` | e.g. `Idle`, `RequestingHeat`, `ProducingHeat`, `RequestingCold` or `ProducingCold` |
| `setPoint`, `roomTemperature` | Current setpoint and room temperature |
| `nextSetpoint`, `nextSwitchTime` | The next setpoint of the clock program and when it starts (local time) |
| `temporaryOverride.endTime` | End of a temporary override (UTC), year 1 when there is none |
| `preHeat` | `enabled` and `active`: whether the zone starts heating early to reach the next setpoint on time. This is part of the climate zone, not the appliance |
| `activeHeatingClimateTimeProgramNumber` | The active clock program, 1 to 3 |
| `controlStrategy` | How the zone is controlled, e.g. `RoomTemperatureOnly` or `Automatic` |
| **Hot water zone** | |
| `dhwType` | `Tank` or `Combi` |
| `dhwZoneMode` | `Scheduling`, `ContinuousComfort`, `Off` or `Boost`, see [hot water zones](#hot-water-zones) |
| `dhwStatus` | e.g. `Idle`, `RequestingHeat`, `ProducingHeat` or `LowTemperature` |
| `dhwTemperature` | Water temperature, `null` for a combi boiler |
| `comfortSetPoint`, `reducedSetpoint`, `targetSetpoint` | The Comfort and Eco setpoints, and the setpoint that applies now |
| `setPointRanges` | Minimum and maximum of the Comfort and Eco setpoints |
| `nextSwitchTime`, `nextSwitchActivity` | When the clock program switches next (local time), and to which activity: `Comfort` or `Reduced` (Eco in the app) |
| `activeDwhTimeProgramNumber` | The active clock program of the hot water zone, `1` on the measured systems |
| `optimizationEnabled` | Whether hot water optimization is enabled. Not reported by every appliance; `capabilityDhwOptimization` of the appliance says whether it supports it. Both `false` on the measured hybrid |
| `boostModeEndTime` | End of a boost (UTC), `null` when not boosting |

<details>
<summary>Example: hybrid heat pump with a combi hot water zone</summary>

```json
{
  "appliances": [
    {
      "applianceId": "00000000-0000-0000-0000-00000000a001",
      "applianceOnline": true,
      "applianceConnectionStatus": "Connected",
      "applianceType": "HeatPump",
      "pairingStatus": "Paired",
      "houseName": "Home",
      "errorStatus": "Running",
      "activeThermalMode": "Idle",
      "operatingMode": "AutomaticHeating",
      "outdoorTemperatureInformation": {
        "outdoorTemperatureSource": "Wired",
        "internetOutdoorTemperature": null,
        "applianceOutdoorTemperature": 14.5,
        "utilizeOutdoorTemperature": null,
        "internetOutdoorTemperatureExpected": false,
        "isDayTime": true,
        "weatherCode": "patchy light rain",
        "cloudOutdoorTemperature": 10,
        "cloudOutdoorTemperatureStatus": "Ok"
      },
      "currentTimestamp": null,
      "holidaySchedule": {
        "startTime": "0001-01-01T00:00:01Z",
        "endTime": "0001-01-01T00:00:01Z",
        "active": false
      },
      "autoFillingMode": "NotAvailable",
      "autoFilling": {
        "mode": "NotAvailable",
        "status": "NotAvailable"
      },
      "waterPressure": 1.7,
      "waterPressureOK": true,
      "capabilityEnergyConsumption": true,
      "capabilityCooling": false,
      "capabilityPreHeat": true,
      "capabilityMultiSchedule": true,
      "capabilityPowerSettings": false,
      "capabilityOutdoorTemperature": true,
      "capabilityUtilizeOutdoorTemperature": false,
      "capabilityInternetOutdoorTemperatureExpected": false,
      "capabilityDhwOptimization": false,
      "hasOverwrittenActivityNames": true,
      "gasCalorificValue": 8.7917,
      "isActive": true,
      "timeZone": "Europe/Amsterdam",
      "seasonalMode": "Winter",
      "hotWaterZones": [
        {
          "hotWaterZoneId": "00000000-0000-0000-0000-00000000d001",
          "applianceId": "00000000-0000-0000-0000-00000000a001",
          "name": "DHW",
          "zoneType": "DHW",
          "dhwZoneMode": "Scheduling",
          "dhwStatus": "Idle",
          "dhwType": "Combi",
          "nextSwitchActivity": "Comfort",
          "capabilityBoostMode": true,
          "dhwTemperature": null,
          "targetSetpoint": 60.0,
          "reducedSetpoint": 10.0,
          "comfortSetPoint": 60.0,
          "setPointMin": 40.0,
          "setPointMax": 65.0,
          "setPointRanges": {
            "comfortSetpointMin": 40.0,
            "comfortSetpointMax": 65.0,
            "reducedSetpointMin": 10.0,
            "reducedSetpointMax": 60.0
          },
          "boostDuration": null,
          "boostModeEndTime": null,
          "nextSwitchTime": "2026-10-22T23:00:00Z",
          "activeDwhTimeProgramNumber": 1,
          "optimizationEnabled": false,
          "antiLegionellaEnabled": null
        }
      ],
      "climateZones": [
        {
          "climateZoneId": "00000000-0000-0000-0000-00000000c001",
          "applianceId": "00000000-0000-0000-0000-00000000a001",
          "name": "Woonkamer",
          "zoneIcon": 3,
          "zoneType": "CH",
          "activeComfortDemand": "Idle",
          "zoneMode": "Manual",
          "controlStrategy": "RoomTemperatureOnly",
          "firePlaceModeActive": false,
          "capabilityFirePlaceMode": true,
          "roomTemperature": 20.0,
          "setPoint": 20.0,
          "nextSetpoint": 20.0,
          "nextSwitchTime": "2026-10-22T22:00:00Z",
          "setPointMin": 5.0,
          "setPointMax": 30.0,
          "currentScheduleSetPoint": 20.0,
          "activeHeatingClimateTimeProgramNumber": 1,
          "capabilityCooling": false,
          "capabilityTemporaryOverrideEndTime": true,
          "preHeat": {
            "enabled": false,
            "active": false
          },
          "temporaryOverride": {
            "endTime": "0001-01-01T00:00:00Z"
          }
        }
      ],
      "solarThermals": []
    }
  ]
}
```
</details>

<details>
<summary>Example: gas boiler</summary>

```json
{
  "appliances": [
    {
      "applianceId": "<appliance uuid>",
      "applianceOnline": true,
      "applianceConnectionStatus": "Connected",
      "applianceType": "Boiler",
      "pairingStatus": "Paired",
      "houseName": "Home",
      "errorStatus": "Running",
      "activeThermalMode": "Idle",
      "operatingMode": "AutomaticHeating",
      "outdoorTemperatureInformation": {
        "outdoorTemperatureSource": "None",
        "internetOutdoorTemperature": null,
        "applianceOutdoorTemperature": null,
        "utilizeOutdoorTemperature": null,
        "internetOutdoorTemperatureExpected": false,
        "isDayTime": true,
        "weatherCode": "light fog",
        "cloudOutdoorTemperature": -2,
        "cloudOutdoorTemperatureStatus": "Ok"
      },
      "currentTimestamp": null,
      "holidaySchedule": {
        "startTime": "0001-01-01T00:00:00Z",
        "endTime": "0001-01-01T00:00:00Z",
        "active": false
      },
      "autoFillingMode": "Disabled",
      "autoFilling": {
        "mode": "Disabled",
        "status": "Standby"
      },
      "waterPressure": 1.4,
      "waterPressureOK": true,
      "capabilityEnergyConsumption": true,
      "capabilityCooling": false,
      "capabilityPreHeat": true,
      "capabilityMultiSchedule": true,
      "capabilityPowerSettings": false,
      "capabilityOutdoorTemperature": true,
      "capabilityUtilizeOutdoorTemperature": false,
      "capabilityInternetOutdoorTemperatureExpected": true,
      "hasOverwrittenActivityNames": true,
      "gasCalorificValue": 10.8134,
      "isActive": true,
      "hotWaterZones": [
        {
          "hotWaterZoneId": "<hot water zone uuid>",
          "applianceId": "<appliance uuid>",
          "name": "DHW",
          "zoneType": "DHW",
          "dhwZoneMode": "Off",
          "dhwStatus": "Idle",
          "dhwType": "Combi",
          "nextSwitchActivity": "Reduced",
          "capabilityBoostMode": true,
          "dhwTemperature": null,
          "targetSetpoint": 60.0,
          "reducedSetpoint": 15.0,
          "comfortSetPoint": 60.0,
          "setPointMin": 40.0,
          "setPointMax": 65.0,
          "setPointRanges": {
            "comfortSetpointMin": 40.0,
            "comfortSetpointMax": 65.0,
            "reducedSetpointMin": 10.0,
            "reducedSetpointMax": 60.0
          },
          "boostDuration": null,
          "boostModeEndTime": null,
          "nextSwitchTime": "2025-02-13T22:00:00Z",
          "activeDwhTimeProgramNumber": 1
        }
      ],
      "climateZones": [
        {
          "climateZoneId": "<climate zone uuid>",
          "applianceId": "<appliance uuid>",
          "name": "Woonkamer",
          "zoneIcon": 3,
          "zoneType": "CH",
          "activeComfortDemand": "Idle",
          "zoneMode": "Scheduling",
          "controlStrategy": "Automatic",
          "firePlaceModeActive": false,
          "capabilityFirePlaceMode": true,
          "roomTemperature": 16.0,
          "setPoint": 16.0,
          "nextSetpoint": 19.0,
          "nextSwitchTime": "2025-02-13T17:30:00Z",
          "setPointMin": 5.0,
          "setPointMax": 30.0,
          "currentScheduleSetPoint": 16.0,
          "activeHeatingClimateTimeProgramNumber": 1,
          "capabilityCooling": false,
          "capabilityTemporaryOverrideEndTime": true,
          "preHeat": {
            "enabled": false,
            "active": false
          },
          "temporaryOverride": {
            "endTime": "0001-01-01T00:00:00Z"
          }
        }
      ],
      "solarThermals": []
    }
  ]
}
```
</details>

## Appliances

### Technical details
```http
GET /appliances/{appliance_id}/technicaldetails
```

Returns the name of the appliance and its gateways.

<details>
<summary>Example response</summary>

```json
{
  "applianceName": "Elga Ace",
  "internetConnectedGateways": [
    {
      "deviceTypeName": "RU2",
      "name": "RU2",
      "serialNumber": "00000000",
      "softwareVersion": "2.28.6",
      "hardwareVersion": "9",
      "controlledZoneName": null
    }
  ],
  "peripherals": []
}
```
</details>

### Holiday mode
```http
POST /appliances/{appliance_id}/holidayschedule
```

Schedules holiday mode. While it is active, the appliance sets every climate zone to `FrostProtection` (setpoint 6 °C) and the hot water to `Off`.
The dashboard reports the result in `holidaySchedule` a few seconds later.

```json
{
  "holidayModeStartTime": "2026-11-20T00:00:00Z",
  "holidayModeEndTime": "2026-11-22T00:00:00Z"
}
```

- Remeha keeps whole days only: a start of `2026-11-20T08:00:00Z` is stored as `2026-11-20T00:00:01Z`.
- The end is the day you come back. The holiday ends at midnight UTC: a holiday until 27 October ended at about 01:00 CET. The dashboard then reports `0001-01-01T00:00:01Z` for both times, like after a cancellation.
- The start must be before the end, otherwise the API returns 400 "Start Date must be before the End Date.".
- The dashboard shows the new dates right away, but `active` only changes a few seconds later, once the appliance itself has switched.

To cancel an active or scheduled holiday, post the empty period. The dashboard then reports `0001-01-01T00:00:01Z` for both times.
```json
{
  "holidayModeStartTime": "0001-01-01T00:00:00Z",
  "holidayModeEndTime": "0001-01-01T00:00:01Z"
}
```
There is no `PUT` or `DELETE` on this path (404).

When the holiday is over, the appliance restores the modes, but not always right away. Measured on a Remeha Elga Ace with one climate zone:
- after a cancellation, a zone in `Manual` came back with its setpoint within 15 seconds;
- after a cancellation, a zone in `Scheduling` came back within 30 seconds once, and was still in `FrostProtection` after 3.5 minutes another time;
- when the holiday ended by itself, a zone in `Scheduling` came back after about 3.5 minutes;
- the hot water came back to `Scheduling` right away.

On a BAXI heat pump, a zone was reported to show `Scheduling` again but keep the 6 °C setpoint until [`modes/schedule`](#climate-zones) was sent again, and the hot water to stay `Off`.
The integration saves the modes when a holiday starts, and sets them again when it is over.

## Climate zones

| Request | Body | Effect |
|---|---|---|
| `POST /climate-zones/{climate_zone_id}/modes/schedule` | `heatingProgramId` | Follow the clock program |
| `POST /climate-zones/{climate_zone_id}/modes/temporary-override` | `roomTemperatureSetPoint` | Override the clock program until its next switch |
| `POST /climate-zones/{climate_zone_id}/modes/manual` | `roomTemperatureSetPoint` | Hold a fixed temperature |
| `POST /climate-zones/{climate_zone_id}/modes/anti-frost` | none | Frost protection (off) |
| `POST /climate-zones/{climate_zone_id}/time-programs/heating/{time_program_id}/activate` | none | Select clock program 1 to 3 |
| `POST /climate-zones/{climate_zone_id}/modes/fireplacemode` | `fireplaceModeActive` | Turn fireplace mode on or off |
| `GET`, `POST /climate-zones/{climate_zone_id}/heating-curve` | `slope`, `baseSetpoint` | Read or change the heating curve |
| `GET /climate-zones/{climate_zone_id}/activities` | | Read the activities of the clock programs |
| `PUT /climate-zones/{climate_zone_id}/activities/heating` | list of activities | Change the temperatures of the heating activities |

### Schedule mode
```http
POST /climate-zones/{climate_zone_id}/modes/schedule
```

Switches the zone to the clock program.
`heatingProgramId` must be the active clock program (`activeHeatingClimateTimeProgramNumber`); it can't select another one.
To select another clock program, see [Select a clock program](#select-a-clock-program).
```json
{
  "heatingProgramId": 1
}
```

### Temporary override
```http
POST /climate-zones/{climate_zone_id}/modes/temporary-override
```

Overrides the clock program with another temperature until its next switch.
The end of the override is in `temporaryOverride.endTime`, in UTC (see [Times](#times)).
```json
{
  "roomTemperatureSetPoint": 20.0
}
```

### Manual mode
```http
POST /climate-zones/{climate_zone_id}/modes/manual
```

Switches the zone to manual mode, which holds the given temperature.
```json
{
  "roomTemperatureSetPoint": 16.0
}
```

### Frost protection
```http
POST /climate-zones/{climate_zone_id}/modes/anti-frost
```

Switches the zone to frost protection, which is off in the app. No body.

### Select a clock program
```http
POST /climate-zones/{climate_zone_id}/time-programs/heating/{time_program_id}/activate
```

Selects clock program `time_program_id` (1 to 3) for schedule mode. No body.

### Fireplace mode
```http
POST /climate-zones/{climate_zone_id}/modes/fireplacemode
```

Turns fireplace mode on or off.
```json
{
  "fireplaceModeActive": true
}
```

### Get the heating curve
```http
GET /climate-zones/{climate_zone_id}/heating-curve
```

Returns the weather-compensated heating curve of the climate zone, its limits, and the maximum flow temperature.
The heating curve sets the flow temperature (the temperature of the water to the radiators or floor heating) from the outdoor temperature:

| Field | Meaning |
|---|---|
| `slope` | How much warmer the flow gets for each degree colder outside |
| `baseSetpoint` | The flow temperature where the curve starts, when it is mild outside |
| `maxFlowTemperature` | The highest flow temperature, however cold it is |
| `minimum…`, `maximum…`, `increment…` | The allowed range and step of `slope` and `baseSetpoint` |

A zone that controls on the room temperature only (`controlStrategy` `RoomTemperatureOnly`) also returns a heating curve. On the measured system, its slope was 0.0.

```json
{
  "slope": 1.1,
  "minimumSlope": 0.0,
  "maximumSlope": 4.0,
  "incrementSlope": 0.1,
  "baseSetpoint": 25.0,
  "minimumBaseSetpoint": 15.0,
  "maximumBaseSetpoint": 70.0,
  "incrementBaseSetpoint": 0.5,
  "maxFlowTemperature": 70.0
}
```

### Change the heating curve
```http
POST /climate-zones/{climate_zone_id}/heating-curve
```

Changes the heating curve. Send both values, also when only one changes.
The values are stored as sent, so round them to their increment: a slope of `1.9` is stored as `1.9`.
```json
{
  "slope": 1.2,
  "baseSetpoint": 20.0
}
```

### Get the activities
```http
GET /climate-zones/{climate_zone_id}/activities
```

Returns the activities of the clock programs, such as home, sleep and away, with their temperatures and limits.
A heat pump with cooling returns its `Cooling` activities first, followed by the `Heating` activities **with the same activity numbers**.
Always match on `type` as well as `activityNumber`.

<details>
<summary>Example response of a heat pump with cooling</summary>

```json
[
  {
    "activityNumber": 1,
    "type": "Cooling",
    "name": "Thuis",
    "temperature": 30.0,
    "setPointMin": 20.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 2,
    "type": "Cooling",
    "name": "Slapen",
    "temperature": 25.0,
    "setPointMin": 20.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 3,
    "type": "Cooling",
    "name": "Afwezig",
    "temperature": 25.0,
    "setPointMin": 20.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 4,
    "type": "Cooling",
    "name": "Werken",
    "temperature": 25.0,
    "setPointMin": 20.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 5,
    "type": "Cooling",
    "name": "Comfort",
    "temperature": 25.0,
    "setPointMin": 20.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 1,
    "type": "Heating",
    "name": "Thuis",
    "temperature": 20.0,
    "setPointMin": 5.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 2,
    "type": "Heating",
    "name": "Slapen",
    "temperature": 20.0,
    "setPointMin": 5.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 3,
    "type": "Heating",
    "name": "Afwezig",
    "temperature": 19.0,
    "setPointMin": 5.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 4,
    "type": "Heating",
    "name": "Werken",
    "temperature": 16.5,
    "setPointMin": 5.0,
    "setPointMax": 30.0,
    "increment": 0.5
  },
  {
    "activityNumber": 5,
    "type": "Heating",
    "name": "Comfort",
    "temperature": 20.0,
    "setPointMin": 5.0,
    "setPointMax": 30.0,
    "increment": 0.5
  }
]
```
</details>

### Change the activity temperatures
```http
PUT /climate-zones/{climate_zone_id}/activities/heating
```

Changes the temperatures of the heating activities.
The integration sends all heating activities, with the changed temperature for one of them.
```json
[
  { "activityNumber": 1, "temperature": 20.5 },
  { "activityNumber": 2, "temperature": 18.0 }
]
```

## Hot water zones
The hot water modes of the Remeha Home app map to these modes and requests:

| App | `dhwZoneMode` | Request |
|---|---|---|
| Schedule | `Scheduling` | `POST /hot-water-zones/{hot_water_zone_id}/modes/schedule` |
| Comfort | `ContinuousComfort` | `POST /hot-water-zones/{hot_water_zone_id}/modes/continuous-comfort` |
| Eco | `Off` | `POST /hot-water-zones/{hot_water_zone_id}/modes/anti-frost` |
| Boost | `Boost` | `POST /hot-water-zones/{hot_water_zone_id}/modes/boost` |

The mode requests have no body.

### Boost
```http
POST /hot-water-zones/{hot_water_zone_id}/modes/boost
```

Heats the water to the Comfort setpoint for a while, 30 minutes on the measured system.
- The API only accepts boost while the zone is in `Scheduling` mode.
- `boostModeEndTime` shows when the boost ends, in UTC (see [Times](#times)).
- To stop a boost, switch to another mode, e.g. `modes/schedule`.

### Comfort temperature
```http
POST /hot-water-zones/{hot_water_zone_id}/comfort-setpoint
```

Sets the temperature of the Comfort mode.
```json
{
  "comfortSetpoint": 60.0
}
```

### Eco temperature
```http
POST /hot-water-zones/{hot_water_zone_id}/reduced-setpoint
```

Sets the temperature of the Eco mode. This only works for a hot water tank (`dhwType` `Tank`).
For a combi boiler, the API returns 400 "Zone must be of type Tank to do this process.": a combi boiler doesn't keep water warm in Eco.
```json
{
  "reducedSetpoint": 45.0
}
```

## Energy consumption

### Get the energy consumption
```http
GET /appliances/{appliance_id}/energyconsumption/{period}
```

Returns the energy consumed and delivered by the appliance, per period: `hourly`, `daily`, `monthly` or `yearly`.
Two query parameters select the periods: `startDate` and `endDate`, e.g. `?startDate=2026-10-22 00:00:00.000Z&endDate=2026-10-22 23:59:59.000Z`.

Each item in `data` is one period:

| Period | Each item covers | `timeStamp` of a completed period | `timeStamp` of the current period |
|---|---|---|---|
| `hourly` | One hour in UTC | Start of the hour | Start of the hour; future hours have `isDataReported: false` |
| `daily` | One **local** calendar day | `<date>T00:00:00+00:00` | Time of the latest data so far |
| `monthly` | One month | Last day of the month | Time of the latest data so far |
| `yearly` | One year | December 31 | Time of the latest data so far |

Each item has the totals of the appliance for heating, hot water and cooling (`…EnergyConsumed` and `…EnergyDelivered`, in kWh), and the figures per heat source in `producerPerformanceStatistics.producers`:
- `producerType`, e.g. `HeatPumpAirSource` or `GasBoiler`, and `energyType`: `Electric` or `NaturalGas`.
- `energyConsumption…` and `energyProduction…` per use: `CH` (central heating), `DHW` (hot water), `Cooling` and `Total`, in kWh.
  Divide the gas energy by `gasCalorificValue` of the [dashboard](#dashboard) to get m³.
- `seasonalEfficiency`: a running seasonal value reported by Remeha, not the efficiency of the period. `null` for a gas boiler.
- A value is `null` when the producer doesn't report it, e.g. the energy delivered by a gas boiler, or hot water for a heat pump when the boiler heats the water.

The appliance totals are not always the sum of the producers: the energy consumed is, but the energy delivered includes Remeha's estimate of the heat delivered by a gas boiler.

> [!NOTE]
> On a hybrid system where the existing gas boiler heats the hot water, such as the Remeha Elga Ace, Remeha reports no gas for hot water: `energyConsumptionDHW` of the gas boiler stays 0.

#### Historical daily consumption

The opt-in `remeha_home.get_energy_history` action reuses the read-only
`/appliances/{id}/energyconsumption/daily` endpoint. The requested
`startDate` and `endDate` are **inclusive local calendar days**. Requests
span at most 366 days and are split into 31-day API batches.

The API's `timeStamp` for a historical record represents a **local calendar
date**, despite the UTC-looking `Z` suffix. The action therefore returns
`date` only, never a misleading UTC instant. Dates are not shifted across
daylight-saving transitions.

The output keeps heat-pump **space-heating** electricity and delivered heating
energy separate from the gas boiler's space-heating input. Hot water and cooling
are intentionally out of scope. Daily `heat_pump_heating_cop` is indicative;
the `period.heat_pump_heating_cop` is computed as the sum of delivered heating
kWh divided by the sum of electrical heating kWh, **not** by averaging daily COP
values. The period ratio and totals are computed over **reported days**, even if
some requested dates are missing. `period.complete`, `days_requested` and
`days_reported` show the coverage. A period total remains `null` if any
reported day lacks the corresponding energy value. COP also remains `null` if
either of its required totals is unavailable or electrical input is zero.
Missing or ambiguous producer values are never treated as zero.

The API reports gas input energy as **kWh**. Existing Home Assistant gas sensors
display **m³** after dividing by the appliance's `gasCalorificValue`, so the
numbers cannot be compared without unit conversion. The action preserves raw
energy units and does not assume today's calorific value was valid historically.

`missing_dates` includes unreported days and conflicting duplicate records.
A warning is logged for each conflicting date; the other dates are still
returned. Public kWh and COP values are rounded to two decimals after
calculating totals. All figures remain Remeha estimates, not calibrated meter
readings; the action does not change sensors or statistics.

#### Daily consumption
- The integration asks for today with local midnight and a `Z` suffix (`<today> 00:00:00.000Z` to `<today> 23:59:59.000Z`), which returns exactly today's item.
  A real UTC window (from 22:00 or 23:00 the day before) also returns yesterday's item.
- The data comes in with a delay of about 2 hours.
- Right after midnight, `data` is empty for about 45 minutes. Until about 02:45, today's item then has all values 0, `isDataReported: false` and no producers.
  After that the real values arrive, including the energy used between 00:00 and 02:00.

<details>
<summary>Example response of a hybrid heat pump with a gas boiler</summary>

```json
{
  "startDateTimeUsed": "2026-10-22T00:00:00+00:00",
  "endDateTimeUsed": "2026-10-22T23:59:59+00:00",
  "data": [
    {
      "isDataReported": true,
      "timeStamp": "2026-10-22T10:00:00+00:00",
      "heatingEnergyConsumed": 5.0,
      "hotWaterEnergyConsumed": 0,
      "coolingEnergyConsumed": 0,
      "heatingEnergyDelivered": 23.0,
      "hotWaterEnergyDelivered": 0,
      "coolingEnergyDelivered": 0,
      "producerPerformanceStatistics": {
        "producers": [
          {
            "isMigratedFromLegacy": false,
            "instanceWithinDevice": 1,
            "deviceIndex": "000000000000",
            "producerType": "HeatPumpAirSource",
            "energyType": "Electric",
            "energyConsumptionCH": 4.0,
            "energyConsumptionDHW": 0,
            "energyConsumptionCooling": 0,
            "energyConsumptionTotal": 4.0,
            "energyProductionCH": 22.0,
            "energyProductionDHW": null,
            "energyProductionCooling": 0,
            "energyProductionTotal": 22.0,
            "seasonalEfficiency": 2.4
          },
          {
            "isMigratedFromLegacy": false,
            "instanceWithinDevice": 2,
            "deviceIndex": "000000000000",
            "producerType": "GasBoiler",
            "energyType": "NaturalGas",
            "energyConsumptionCH": 1.0,
            "energyConsumptionDHW": 0,
            "energyConsumptionCooling": 0,
            "energyConsumptionTotal": 1.0,
            "energyProductionCH": null,
            "energyProductionDHW": null,
            "energyProductionCooling": null,
            "energyProductionTotal": null,
            "seasonalEfficiency": null
          }
        ]
      }
    }
  ]
}
```
</details>
