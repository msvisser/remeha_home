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
      "activeThermalMode": "Idle",
      "applianceConnectionStatus": "Connected",
      "applianceId": "<appliance uuid>",
      "applianceOnline": true,
      "applianceType": "Boiler",
      "autoFilling": {
        "mode": "Disabled",
        "status": "Standby"
      },
      "autoFillingMode": "Disabled",
      "capabilityCooling": false,
      "capabilityEnergyConsumption": true,
      "capabilityMultiSchedule": true,
      "capabilityPowerSettings": false,
      "capabilityPreHeat": true,
      "capabilityUtilizeOutdoorTemperature": false,
      "climateZones": [
        {
          "activeComfortDemand": "Idle",
          "activeHeatingClimateTimeProgramNumber": 1,
          "applianceId": "<appliance uuid>",
          "capabilityCooling": false,
          "capabilityFirePlaceMode": true,
          "climateZoneId": "<climate zone uuid>",
          "currentScheduleSetPoint": 16,
          "firePlaceModeActive": false,
          "name": "Woonkamer",
          "nextSetpoint": 19,
          "nextSwitchTime": "2022-11-19T17:00:00Z",
          "preHeat": {
            "active": false,
            "enabled": false
          },
          "roomTemperature": 16,
          "setPoint": 16,
          "setPointMax": 30,
          "setPointMin": 5,
          "zoneIcon": 3,
          "zoneMode": "Scheduling",
          "zoneType": "CH"
        }
      ],
      "currentTimestamp": null,
      "errorStatus": "Running",
      "gasCalorificValue": null,
      "hasOverwrittenActivityNames": false,
      "holidaySchedule": {
        "active": false,
        "endTime": "0001-01-01T00:00:00Z",
        "startTime": "0001-01-01T00:00:00Z"
      },
      "hotWaterZones": [
        {
          "activeDwhTimeProgramNumber": 1,
          "applianceId": "<appliance uuid>",
          "boostDuration": null,
          "boostModeEndTime": null,
          "capabilityBoostMode": false,
          "comfortSetPoint": 60,
          "dhwStatus": "Idle",
          "dhwTemperature": 27.7,
          "dhwType": "Combi",
          "dhwZoneMode": "Scheduling",
          "hotWaterZoneId": "<hot water zone uuid>",
          "name": "DHW",
          "nextSwitchActivity": "Reduced",
          "nextSwitchTime": "2022-11-19T22:00:00Z",
          "reducedSetpoint": 15,
          "setPointMax": 65,
          "setPointMin": 45,
          "setPointRanges": {
            "comfortSetpointMax": 65,
            "comfortSetpointMin": 45,
            "reducedSetpointMax": 45,
            "reducedSetpointMin": 25
          },
          "targetSetpoint": 60,
          "zoneType": "DHW"
        }
      ],
      "houseName": "Home",
      "operatingMode": "AutomaticHeating",
      "outdoorTemperature": null,
      "outdoorTemperatureInformation": {
        "applianceOutdoorTemperature": null,
        "cloudOutdoorTemperature": 2,
        "cloudOutdoorTemperatureStatus": "Ok",
        "internetOutdoorTemperature": null,
        "isDayTime": true,
        "outdoorTemperatureSource": "Unknown",
        "utilizeOutdoorTemperature": null,
        "weatherCode": "Sunny"
      },
      "outdoorTemperatureSource": "Unknown",
      "pairingStatus": "Paired",
      "waterPressure": 1.5,
      "waterPressureOK": true
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

## GET `appliances/{appliance_id}/energyconsumption/daily`
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

## GET `appliances/{appliance_id}/energyconsumption/monthly`
Get the monthly energy consumption of the appliance.
See `daily` for the response format.

## GET `appliances/{appliance_id}/energyconsumption/yearly`
Get the yearly energy consumption of the appliance.
See `daily` for the response format.


## POST `/hot-water-zones/{hot_water_zone_id}/modes/continuous-comfort`
Set the hot water to comfort mode

## POST `/hot-water-zones/{hot_water_zone_id}/modes/schedule`
Set the hot water to schedule mode

## POST `/hot-water-zones/{hot_water_zone_id}/modes/anti-frost`
Set the hot water to eco mode, in fact off.

