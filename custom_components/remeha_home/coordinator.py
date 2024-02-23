"""Coordinator for fetching the Remeha Home data."""
from datetime import datetime, timedelta
import logging

import async_timeout
from aiohttp.client_exceptions import ClientResponseError

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import RemehaHomeAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RemehaHomeUpdateCoordinator(DataUpdateCoordinator):
    """Remeha Home update coordinator."""

    def __init__(self, hass: HomeAssistantType, api: RemehaHomeAPI) -> None:
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
            async with async_timeout.timeout(30):
                data = await self.api.async_get_dashboard()
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
                self.technical_info[
                    appliance_id
                ] = await self.api.async_get_appliance_technical_information(
                    appliance_id
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
                        self.appliance_consumption_data[
                            appliance_id
                        ] = consumption_data["data"][0]
                    else:
                        _LOGGER.warning(
                            "No consumption data found for appliance %s", appliance_id
                        )
                        self.appliance_consumption_data[appliance_id] = {
                            "heatingEnergyConsumed": 0.0,
                            "hotWaterEnergyConsumed": 0.0,
                            "coolingEnergyConsumed": 0.0,
                            "heatingEnergyDelivered": 0.0,
                            "hotWaterEnergyDelivered": 0.0,
                            "coolingEnergyDelivered": 0.0,
                        }

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
                appliance["consumptionData"] = {
                    "heatingEnergyConsumed": 0.0,
                    "hotWaterEnergyConsumed": 0.0,
                    "coolingEnergyConsumed": 0.0,
                    "heatingEnergyDelivered": 0.0,
                    "hotWaterEnergyDelivered": 0.0,
                    "coolingEnergyDelivered": 0.0,
                }

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

    def _is_change_of_day(self, last_consumption_timestamp):
        if not last_consumption_timestamp:
            return False
        today = datetime.date.today()
        last_consumption_date = last_consumption_timestamp["timeStamp"][:-15]
        last_consumption_date = datetime.datetime.strptime(
            last_consumption_date, "%y-%m-%dT%H:%M:%S"
        )
        return today != last_consumption_date.date()

    def get_by_id(self, item_id: str):
        """Return item with the specified item id."""
        return self.items.get(item_id)

    def get_device_info(self, item_id: str):
        """Return device info for the item with the specified id."""
        return self.device_info.get(item_id)
    
class RemehaHomeUpdatePowerCoordinator(DataUpdateCoordinator):
    """Remeha Home power update coordinator."""

    def __init__(self, hass: HomeAssistantType, api: RemehaHomeAPI) -> None:
        """Initialize Remeha Home power update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=600),
        )
        self.api = api
        self.items = {}
        self.device_info = {}
        self.technical_info = {}

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                data = await self.api.async_get_dashboard()
        except ClientResponseError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            if err.status == 401:
                raise ConfigEntryAuthFailed from err

            raise UpdateFailed from err

        for appliance in data["appliances"]:
            appliance_id = appliance["applianceId"]
            self.items[appliance_id] = appliance

            consumption_data = await self.api.async_get_consumption_data(appliance_id)
            is_change_of_day = self._is_change_of_day(appliance.get("consumption_data", {}).get('timeStamp'))
            appliance["consumption_data"] = consumption_data["data"][-1] \
                if consumption_data["data"] \
                else {"heatingEnergyConsumed":0, "hotWaterEnergyConsumed":0,"coolingEnergyConsumed":0, "heatingEnergyDelivered":0,"hotWaterEnergyDelivered":0, "coolingEnergyDelivered":0}
            if is_change_of_day:
                # Total increase sensors must be reset to 0 every day
                appliance["consumption_data"]["heatingEnergyConsumed"] = 0
                appliance["consumption_data"]["hotWaterEnergyConsumed"] = 0
                appliance["consumption_data"]["coolingEnergyConsumed"] = 0
                appliance["consumption_data"]["heatingEnergyDelivered"] = 0
                appliance["consumption_data"]["hotWaterEnergyDelivered"] = 0
                appliance["consumption_data"]["coolingEnergyDelivered"] = 0
        return data

    def _is_change_of_day(self, last_consumption_timestamp):
        if not last_consumption_timestamp:
            return False
        today = datetime.date.today()
        last_consumption_date = last_consumption_timestamp["timeStamp"][:-15]
        last_consumption_date = datetime.datetime.strptime(
            last_consumption_date, "%y-%m-%dT%H:%M:%S"
        )
        return today != last_consumption_date.date()

    def get_by_id(self, item_id: str):
        """Return item with the specified item id."""
        return self.items.get(item_id)

    def get_device_info(self, item_id: str):
        """Return device info for the item with the specified id."""
        return self.device_info.get(item_id)

