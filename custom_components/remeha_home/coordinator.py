"""Coordinator for fetching the Remeha Home data."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import logging

import asyncio
from aiohttp.client_exceptions import ClientResponseError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import RemehaHomeAPI
from .const import DOMAIN
from .util import detect_dhw_setpoint_activity

_LOGGER = logging.getLogger(__name__)

PRODUCER_TYPE_NAMES = {
    "HeatPumpAirSource": "Heat Pump (Air Source)",
    "HeatPumpGroundSource": "Heat Pump (Ground Source)",
    "HeatPumpWaterSource": "Heat Pump (Water Source)",
    "GasBoiler": "Gas Boiler",
    "OilBoiler": "Oil Boiler",
    "ElectricBoiler": "Electric Boiler",
    "CHP": "CHP",
}

PRODUCER_STATS = [
    "energyConsumptionCH",
    "energyConsumptionDHW",
    "energyConsumptionCooling",
    "energyConsumptionTotal",
    "energyProductionCH",
    "energyProductionDHW",
    "energyProductionCooling",
    "energyProductionTotal",
]

APPLIANCE_CONSUMPTION_DEFAULT_DATA = {
    "heatingEnergyConsumed": 0.0,
    "hotWaterEnergyConsumed": 0.0,
    "coolingEnergyConsumed": 0.0,
    "heatingEnergyDelivered": 0.0,
    "hotWaterEnergyDelivered": 0.0,
    "coolingEnergyDelivered": 0.0,
}


def get_producers(consumption: dict) -> list[dict]:
    """Return the producers (heat sources) in the consumption data of an appliance."""
    producer_stats = consumption.get("producerPerformanceStatistics")
    return (producer_stats or {}).get("producers") or []


def get_producer_id(appliance_id: str, producer: dict) -> str:
    """Return the item id of a producer."""
    return f"{appliance_id}_{producer['instanceWithinDevice']}"


class RemehaHomeUpdateCoordinator(DataUpdateCoordinator):
    """Remeha Home update coordinator."""

    def __init__(self, hass: HomeAssistant, api: RemehaHomeAPI) -> None:
        """Initialize Remeha Home update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.api = api
        self.items = {}
        self.device_info = {}
        self.technical_info = {}
        self.appliance_consumption_data = {}
        self.appliance_last_consumption_data_update = {}
        # Date of the last non-empty consumption data, to tell an empty response
        # during the day apart from the start of a new day
        self.appliance_consumption_data_date: dict[str, date] = {}
        self.appliance_producer_ids: dict[str, set[str]] = {}
        self.dhw_activity_cache = {}
        self.heating_curve_data: dict[str, dict] = {}
        self.activities_data: dict[str, list] = {}

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with asyncio.timeout(30):
                data = await self.api.async_get_dashboard()
                _LOGGER.debug("Requested dashboard information: %s", data)
        except ClientResponseError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            if err.status == 401:
                raise ConfigEntryAuthFailed from err

            raise UpdateFailed from err

        # Save the current time for appliance usage data updates
        now = datetime.now()

        for appliance in data["appliances"]:
            appliance_id = appliance["applianceId"]
            self.items[appliance_id] = appliance

            # Request appliance technical information the first time it is discovered
            if appliance_id not in self.technical_info:
                self.technical_info[appliance_id] = (
                    await self.api.async_get_appliance_technical_information(
                        appliance_id
                    )
                )
                _LOGGER.debug(
                    "Requested technical information for appliance %s: %s",
                    appliance_id,
                    self.technical_info[appliance_id],
                )

            # Only update appliance usage data every 15 minutes
            if (appliance_id not in self.appliance_last_consumption_data_update) or (
                now - self.appliance_last_consumption_data_update[appliance_id]
                >= timedelta(minutes=14, seconds=45)
            ):
                try:
                    consumption_data = (
                        await self.api.async_get_consumption_data_for_today(
                            appliance_id
                        )
                    )
                    _LOGGER.debug(
                        "Requested consumption data for appliance %s: %s",
                        appliance_id,
                        consumption_data,
                    )

                    if len(consumption_data["data"]) > 0:
                        consumption = self._process_consumption_data(
                            appliance, consumption_data["data"][0]
                        )
                        self.appliance_consumption_data_date[appliance_id] = now.date()
                    elif self.appliance_consumption_data_date.get(appliance_id) == now.date():
                        # Empty response during the day: keep today's values, a drop to 0
                        # would be seen as a reset and double count the day's consumption
                        _LOGGER.debug(
                            "No consumption data found for appliance %s, keeping today's values",
                            appliance_id,
                        )
                        consumption = self.appliance_consumption_data[appliance_id]
                    else:
                        # Normal right after midnight, before the API has data for today
                        _LOGGER.debug(
                            "No consumption data found for appliance %s", appliance_id
                        )
                        consumption = dict(APPLIANCE_CONSUMPTION_DEFAULT_DATA)

                    self.appliance_consumption_data[appliance_id] = consumption
                    self.appliance_last_consumption_data_update[appliance_id] = now
                except ClientResponseError as err:
                    _LOGGER.warning(
                        "Failed to request consumption data for appliance %s: %s",
                        appliance_id,
                        err,
                    )
                except Exception:
                    # Consumption data is optional, so a problem with it must never
                    # fail the whole update and make the climate entities unavailable.
                    # Keep the previous data and retry at the next consumption interval.
                    _LOGGER.exception(
                        "Failed to update consumption data for appliance %s",
                        appliance_id,
                    )
                    self.appliance_last_consumption_data_update[appliance_id] = now

            # Get the cached consumption data for the appliance or use default values
            if appliance_id in self.appliance_consumption_data:
                appliance["consumptionData"] = self.appliance_consumption_data[
                    appliance_id
                ]
            else:
                appliance["consumptionData"] = dict(APPLIANCE_CONSUMPTION_DEFAULT_DATA)

            self.device_info[appliance_id] = DeviceInfo(
                identifiers={(DOMAIN, appliance_id)},
                name=appliance["houseName"],
                manufacturer="Remeha",
                model=self.technical_info[appliance_id]["applianceName"],
            )

            for climate_zone in appliance["climateZones"]:
                climate_zone_id = climate_zone["climateZoneId"]
                # This assumes that all climate zones for an appliance share the same gateway
                gateways = self.technical_info[appliance_id][
                    "internetConnectedGateways"
                ]

                if len(gateways) > 1:
                    _LOGGER.warning(
                        "Appliance %s has more than one gateway, using technical information from the first one",
                        appliance_id,
                    )

                if len(gateways) > 0:
                    gateway_info = gateways[0]
                else:
                    _LOGGER.warning(
                        "Appliance %s has no gateways, using unknown values",
                        appliance_id,
                    )
                    gateway_info = {
                        "name": "Unknown",
                        "hardwareVersion": "Unknown",
                        "softwareVersion": "Unknown",
                    }

                self.items[climate_zone_id] = climate_zone

                # Fetch heating curve data once (re-fetched after writes)
                if climate_zone_id not in self.heating_curve_data:
                    try:
                        self.heating_curve_data[climate_zone_id] = (
                            await self.api.async_get_heating_curve(climate_zone_id)
                        )
                        _LOGGER.debug(
                            "Requested heating curve data for climate zone %s: %s",
                            climate_zone_id,
                            self.heating_curve_data[climate_zone_id],
                        )
                    except ClientResponseError as err:
                        _LOGGER.warning(
                            "Failed to request heating curve data for climate zone %s: %s",
                            climate_zone_id,
                            err,
                        )

                # Fetch activities data once (re-fetched after writes)
                if climate_zone_id not in self.activities_data:
                    try:
                        self.activities_data[climate_zone_id] = (
                            await self.api.async_get_activities(climate_zone_id)
                        )
                        _LOGGER.debug(
                            "Requested activities data for climate zone %s: %s",
                            climate_zone_id,
                            self.activities_data[climate_zone_id],
                        )
                    except ClientResponseError as err:
                        _LOGGER.warning(
                            "Failed to request activities data for climate zone %s: %s",
                            climate_zone_id,
                            err,
                        )

                self.device_info[climate_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, climate_zone_id)},
                    name=climate_zone["name"],
                    manufacturer="Remeha",
                    model=gateway_info["name"],
                    hw_version=gateway_info["hardwareVersion"],
                    sw_version=gateway_info["softwareVersion"],
                    via_device=(DOMAIN, appliance_id),
                )

            for hot_water_zone in appliance["hotWaterZones"]:
                hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
                hot_water_zone["dhwCurrentActivity"] = self._derive_dhw_activity(
                    hot_water_zone
                )

                self.items[hot_water_zone_id] = hot_water_zone
                self.device_info[hot_water_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, hot_water_zone_id)},
                    name=hot_water_zone["name"],
                    manufacturer="Remeha",
                    model="Hot Water Zone",
                    via_device=(DOMAIN, appliance_id),
                )

            self._update_producers(
                appliance_id, get_producers(appliance["consumptionData"])
            )
        return data

    def _update_producers(self, appliance_id: str, producers: list[dict]) -> None:
        """Register the producers (heat sources) of an appliance as devices."""
        type_counts = Counter(producer.get("producerType") for producer in producers)
        current_ids = set()

        for producer in producers:
            producer_id = get_producer_id(appliance_id, producer)
            current_ids.add(producer_id)
            self.items[producer_id] = producer

            producer_type = producer.get("producerType", "Producer")
            producer_label = PRODUCER_TYPE_NAMES.get(producer_type, producer_type)
            # Only number the producers when there are several of the same type
            if type_counts[producer_type] > 1:
                name = f"{producer_label} {producer['instanceWithinDevice']}"
            else:
                name = producer_label
            self.device_info[producer_id] = DeviceInfo(
                identifiers={(DOMAIN, producer_id)},
                name=name,
                manufacturer="Remeha",
                model=producer_label,
                via_device=(DOMAIN, appliance_id),
            )

        # Right after midnight the API doesn't list the producers until the data
        # for the new day is reported. Their values for the new day are 0, not the
        # values of yesterday. The seasonal efficiency is kept, it's a running value.
        known_ids = self.appliance_producer_ids.setdefault(appliance_id, set())
        for producer_id in known_ids - current_ids:
            self.items[producer_id] = {
                **self.items[producer_id],
                **dict.fromkeys(PRODUCER_STATS, 0.0),
            }
        known_ids |= current_ids

    def _process_consumption_data(self, appliance: dict, consumption: dict) -> dict:
        """Prepare the consumption data of an appliance and its producers."""
        # Start from the defaults so a missing appliance total is 0.0 instead of unknown
        consumption = {**APPLIANCE_CONSUMPTION_DEFAULT_DATA, **consumption}

        for producer in get_producers(consumption):
            # The API reports null for energy a producer doesn't use or deliver, e.g.
            # hot water for a heat pump when the boiler heats the water
            for producer_stat in PRODUCER_STATS:
                if not isinstance(producer.get(producer_stat), int | float):
                    producer[producer_stat] = 0.0

            if producer.get("energyType") == "NaturalGas":
                # Recalculate energy values back to gas values when Gas device
                calorific_value = float(appliance["gasCalorificValue"])
                for key in ("energyConsumptionCH", "energyConsumptionDHW"):
                    producer[key] = round(producer[key] / calorific_value, 2)

        return consumption

    def get_by_id(self, item_id: str):
        """Return item with the specified item id."""
        return self.items.get(item_id)

    def get_device_info(self, item_id: str):
        """Return device info for the item with the specified id."""
        return self.device_info.get(item_id)

    def get_heating_curve(self, climate_zone_id: str) -> dict | None:
        """Return heating curve data for the specified climate zone."""
        return self.heating_curve_data.get(climate_zone_id)

    def get_activities(self, climate_zone_id: str) -> list | None:
        """Return activities data for the specified climate zone."""
        return self.activities_data.get(climate_zone_id)

    def _derive_dhw_activity(self, zone: dict) -> str | None:
        """Derive a human-friendly DHW activity label."""
        mode = zone.get("dhwZoneMode")
        if mode in ("ContinuousComfort", "Boost"):
            activity = "Comfort"
            self.dhw_activity_cache[zone.get("hotWaterZoneId")] = activity
            return activity
        if mode == "Scheduling":
            activity = detect_dhw_setpoint_activity(
                zone.get("targetSetpoint"),
                zone.get("comfortSetPoint"),
                zone.get("reducedSetpoint"),
            )
            if activity is not None:
                self.dhw_activity_cache[zone.get("hotWaterZoneId")] = activity
                return activity
            return self.dhw_activity_cache.get(zone.get("hotWaterZoneId"))
        if mode == "Off":
            activity = "Anti-Frost"
            self.dhw_activity_cache[zone.get("hotWaterZoneId")] = activity
            return activity
        return None
