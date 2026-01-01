# Remeha Home API
__All of the following information was obtained by sniffing the app traffic.__
__Please use this information responsibly.__

The API used by the Remeha Home app is located at `https://api.bdrthermea.net/Mobile/api/`.
To make requests to the API, a valid OAuth2 token is required.
This token can be obtained by authenticating with BDR B2C OAuth2 API.

All API requests should have the following two headers:
```
Authorization: Bearer <token>
Ocp-Apim-Subscription-Key: df605c5470d846fc91e848b1cc653ddf
```

Each of the following sections gives an example of the output for the different endpoints.

## GET `/homes/dashboard`
This endpoint is used to get the dashboard information that is shown when the app is first opened.

Response:
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

```json
{
    "appliances": [
        {
            "applianceId": "<appliance uuid>",
            "applianceOnline": "True",
            "applianceConnectionStatus": "Connected",
            "applianceType": "HeatPump",
            "pairingStatus": "Paired",
            "houseName": "Home",
            "errorStatus": "Running",
            "activeThermalMode": "Cooling",
            "operatingMode": "AutomaticHeating",
            "outdoorTemperatureInformation": {
                "outdoorTemperatureSource": "Wired",
                "internetOutdoorTemperature": "None",
                "applianceOutdoorTemperature": 24.5,
                "utilizeOutdoorTemperature": "None",
                "internetOutdoorTemperatureExpected": "False",
                "isDayTime": "True",
                "weatherCode": "Sunny",
                "cloudOutdoorTemperature": 22,
                "cloudOutdoorTemperatureStatus": "Ok"
            },
            "currentTimestamp": "None",
            "holidaySchedule": {
                "startTime": "0001-01-01T00: 00: 00Z",
                "endTime": "0001-01-01T00: 00: 00Z",
                "active": "False"
            },
            "autoFillingMode": "NotAvailable",
            "autoFilling": {
                "mode": "NotAvailable",
                "status": "NotAvailable"
            },
            "waterPressure": 1.4,
            "waterPressureOK": "True",
            "capabilityEnergyConsumption": "True",
            "capabilityCooling": "False",
            "capabilityPreHeat": "True",
            "capabilityMultiSchedule": "True",
            "capabilityPowerSettings": "False",
            "capabilityOutdoorTemperature": "True",
            "capabilityUtilizeOutdoorTemperature": "False",
            "capabilityInternetOutdoorTemperatureExpected": "False",
            "hasOverwrittenActivityNames": "False",
            "gasCalorificValue": 8.7917,
            "isActive": "True",
            "timeZone": "None",
            "hotWaterZones": [],
            "climateZones": [
                {
                    "climateZoneId": "<climate zone uuid>",
                    "applianceId": "<appliance uuid>",
                    "name": "Woonkamer",
                    "zoneIcon": 3,
                    "zoneType": "CH",
                    "activeComfortDemand": "ProducingCold",
                    "zoneMode": "Manual",
                    "controlStrategy": "Automatic",
                    "firePlaceModeActive": "False",
                    "capabilityFirePlaceMode": "True",
                    "roomTemperature": 23.5,
                    "setPoint": 21.0,
                    "nextSetpoint": 30.0,
                    "nextSwitchTime": "2025-06-21T22: 00: 00Z",
                    "setPointMin": 5.0,
                    "setPointMax": 30.0,
                    "currentScheduleSetPoint": 22.0,
                    "activeHeatingClimateTimeProgramNumber": 1,
                    "capabilityCooling": "False",
                    "capabilityTemporaryOverrideEndTime": "True",
                    "preHeat": {
                        "enabled": "False",
                        "active": "False"
                    },
                    "temporaryOverride": {
                        "endTime": "0001-01-01T00: 00: 00Z"
                    }
                }
            ],
            "solarThermals": []
        }
    ]
}
```

## POST `/climate-zones/{climate_zone_id}/modes/manual`
Set the climate zone to manual mode.

Request:
```json
{
  "roomTemperatureSetPoint": 16.0
}
```

## POST `/climate-zones/{climate_zone_id}/modes/schedule`
Set the climate zone to schedule mode.
The `heatingProgramId` should match the currently selected heating program, but cannot be used to change the heating program.
For changing the heating program, see the `/climate-zones/{climate_zone_id}/time-programs/heating/{time_program_id}/activate` api.

Request:
```json
{
  "heatingProgramId": 1
}
```

## POST `/climate-zones/{climate_zone_id}/modes/temporary-override`
Set the climate zone to temporary override mode.

Request:
```json
{
  "roomTemperatureSetPoint": 20.0
}
```

## POST `/climate-zones/{climate_zone_id}/modes/anti-frost`
Set the climate zone to anti-frost (off) mode.

## POST `/climate-zones/{climate_zone_id}/time-programs/heating/{time_program_id}/activate`
Activate a time program for the schedule mode.

## POST `/climate-zones/{climate_zone_id}/modes/fireplacemode`
Enable or disable fireplace mode.

Request:
```json
{
  "fireplaceModeActive": true
}
```

## POST `/hot-water-zones/{hot_water_zone_id}/modes/anti-frost`
Switch to the Eco mode for the hot water zone.

## POST `/hot-water-zones/{hot_water_zone_id}/modes/schedule`
Switch to the Schedule mode for the hot water zone.

## POST `/hot-water-zones/{hot_water_zone_id}/modes/continuous-comfort`
Switch to the Comfort mode for the hot water zone.

## POST `/hot-water-zones/{hot_water_zone_id}/reduced-setpoint`
Set the target temperature of the Eco mode for the hot water zone.

Request:
```json
{
  "reducedSetpoint": 45.0
}
```

## POST `/hot-water-zones/{hot_water_zone_id}/comfort-setpoint`
Set the target temperature of the Comfort mode for the hot water zone.

Request:
```json
{
  "comfortSetpoint": 60.0
}
```

## GET `/appliances/{appliance_id}/energyconsumption/daily`
Get the daily energy consumption of the appliance.
This request requires two query parameters, `startDate` and `endDate`, which should contain an ISO-8601 timestamp, e.g. `2023-01-03 00:00:00.000Z`.

Response:
```json
{
  "startDateTimeUsed": "2023-01-03T00:00:00+00:00",
  "endDateTimeUsed": "2023-02-13T00:00:00+00:00",
  "data": [
    {
      "timeStamp": "2023-01-03T00:00:00+00:00",
      "heatingEnergyConsumed": 3.00,
      "hotWaterEnergyConsumed": 3.00,
      "coolingEnergyConsumed": 0,
      "heatingEnergyDelivered": 0,
      "hotWaterEnergyDelivered": 0,
      "coolingEnergyDelivered": 0
    },
    ...
  ]
}
```

## GET `/appliances/{appliance_id}/energyconsumption/monthly`
Get the monthly energy consumption of the appliance.
See `daily` for the response format.

## GET `/appliances/{appliance_id}/energyconsumption/yearly`
Get the yearly energy consumption of the appliance.
See `daily` for the response format.
