"""Coordinator for fetching the Remeha Home data."""

from datetime import datetime, timedelta
import logging

import asyncio
from aiohttp.client_exceptions import ClientResponseError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import RemehaHomeAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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
                        self.appliance_consumption_data[appliance_id] = (
                            consumption_data["data"][0]
                        )
                    else:
                        _LOGGER.warning(
                            "No consumption data found for appliance %s", appliance_id
                        )
                        self.appliance_consumption_data[appliance_id] = (
                            APPLIANCE_CONSUMPTION_DEFAULT_DATA
                        )

                    if (
                        "producerPerformanceStatistics"
                        in self.appliance_consumption_data[appliance_id]
                    ):
                        for producer in self.appliance_consumption_data[appliance_id][
                            "producerPerformanceStatistics"
                        ]["producers"]:
                            for producer_stat in PRODUCER_STATS:
                                stat = f"{producer_stat}{producer["energyType"]}"
                                value = producer.get(producer_stat, 0.0)
                                if not isinstance(value, int | float):
                                    value = 0.0

                                self.appliance_consumption_data[appliance_id][stat] = (
                                    self.appliance_consumption_data[appliance_id].get(
                                        stat, 0.0
                                    )
                                    + value
                                )

                            self.appliance_consumption_data[appliance_id][
                                f"seasonalEfficiency{producer["energyType"]}"
                            ] = producer.get("seasonalEfficiency", 0.0)

                    self.appliance_last_consumption_data_update[appliance_id] = now
                except ClientResponseError as err:
                    _LOGGER.warning(
                        "Failed to request consumption data for appliance %s: %s",
                        appliance_id,
                        err,
                    )

            # Get the cached consumption data for the appliance or use default values
            if appliance_id in self.appliance_consumption_data:
                appliance["consumptionData"] = self.appliance_consumption_data[
                    appliance_id
                ]
            else:
                appliance["consumptionData"] = APPLIANCE_CONSUMPTION_DEFAULT_DATA

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
                self.items[hot_water_zone_id] = hot_water_zone
                self.device_info[hot_water_zone_id] = DeviceInfo(
                    identifiers={(DOMAIN, hot_water_zone_id)},
                    name=hot_water_zone["name"],
                    manufacturer="Remeha",
                    model="Hot Water Zone",
                    via_device=(DOMAIN, appliance_id),
                )

        return data

    def get_by_id(self, item_id: str):
        """Return item with the specified item id."""
        return self.items.get(item_id)

    def get_device_info(self, item_id: str):
        """Return device info for the item with the specified id."""
        return self.device_info.get(item_id)
