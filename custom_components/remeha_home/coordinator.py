"""Coordinator for fetching the Remeha Home data."""

from __future__ import annotations

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
    "energyConsumptionCHElectric": 0.0,
    "energyConsumptionDHWElectric": 0.0,
    "energyConsumptionCoolingElectric": 0.0,
    "energyConsumptionTotalElectric": 0.0,
    "energyProductionCHElectric": 0.0,
    "energyProductionDHWElectric": 0.0,
    "energyProductionCoolingElectric": 0.0,
    "energyProductionTotalElectric": 0.0,
    "energyConsumptionCHNaturalGas": 0.0,
    "energyConsumptionDHWNaturalGas": 0.0,
    "energyConsumptionCoolingNaturalGas": 0.0,
    "energyConsumptionTotalNaturalGas": 0.0,
    "energyProductionCHNaturalGas": 0.0,
    "energyProductionDHWNaturalGas": 0.0,
    "energyProductionCoolingNaturalGas": 0.0,
    "energyProductionTotalNaturalGas": 0.0,
    "seasonalEfficiencyElectric": 0.0,
}


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

            producer_stats = appliance["consumptionData"].get("producerPerformanceStatistics")
            if producer_stats and len(producer_stats.get("producers") or []) > 1:
                for producer in producer_stats["producers"]:
                    producer_id = "{0}_{1}".format(appliance_id, producer["instanceWithinDevice"])
                    self.items[producer_id] = producer
                    producer_type = producer["producerType"]
                    producer_label = PRODUCER_TYPE_NAMES.get(producer_type, producer_type)
                    instance = producer["instanceWithinDevice"]
                    self.device_info[producer_id] = DeviceInfo(
                        identifiers={(DOMAIN, producer_id)},
                        name=f"{producer_label} {instance}",
                        manufacturer="Remeha",
                        model=producer_type,
                        via_device=(DOMAIN, appliance_id),
                    )
        return data

    def _process_consumption_data(self, appliance: dict, consumption: dict) -> dict:
        """Convert gas producer values and add totals per energy type."""
        # Start from the defaults so the totals per energy type are 0.0 instead of
        # missing when the API returns a bucket without producers, which it does
        # right after midnight until the data for the new day is reported
        consumption = {**APPLIANCE_CONSUMPTION_DEFAULT_DATA, **consumption}
        producer_stats = consumption.get("producerPerformanceStatistics") or {}
        producers = producer_stats.get("producers") or []

        for producer in producers:
            if producer.get("energyType") == "NaturalGas":
                # Recalculate energy values back to gas values when Gas device
                calorific_value = float(appliance["gasCalorificValue"])
                for key in ("energyConsumptionCH", "energyConsumptionDHW"):
                    producer[key] = round(
                        float(producer.get(key) or 0.0) / calorific_value, 2
                    )

        for producer in producers:
            energy_type = producer.get("energyType")
            for producer_stat in PRODUCER_STATS:
                stat = f"{producer_stat}{energy_type}"
                value = producer.get(producer_stat, 0.0)
                if not isinstance(value, int | float):
                    value = 0.0

                consumption[stat] = consumption.get(stat, 0.0) + value

            consumption[f"seasonalEfficiency{energy_type}"] = producer.get(
                "seasonalEfficiency", 0.0
            )

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
