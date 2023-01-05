from datetime import timedelta
import logging

import async_timeout
from aiohttp.client_exceptions import ClientResponseError

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
        self.climate_zones = {}

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                data = await self.api.async_get_dashboard()
        except ClientResponseError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            if err.status == 401:
                raise ConfigEntryAuthFailed from err

            raise UpdateFailed from err

        for appliance in data["appliances"]:
            for climate_zone in appliance["climateZones"]:
                self.climate_zones[climate_zone["climateZoneId"]] = climate_zone

        return data

    def get_climate_zone(self, climate_zone_id: str):
        """Return climate zone with the specified climate zone id."""
        return self.climate_zones.get(climate_zone_id)
