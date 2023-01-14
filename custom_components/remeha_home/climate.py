"""Platform for Remeha Home climate integration."""
from __future__ import annotations
from typing import Any
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RemehaHomeAPI
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

REMEHA_MODE_TO_HVAC_MODE = {
    "Scheduling": HVACMode.AUTO,
    "TemporaryOverride": HVACMode.AUTO,
    "Manual": HVACMode.HEAT,
    "FrostProtection": HVACMode.OFF,
}

HVAC_MODE_TO_REMEHA_MODE = {
    HVACMode.AUTO: "Scheduling",
    HVACMode.HEAT: "Manual",
    HVACMode.OFF: "FrostProtection",
}

REMEHA_STATUS_TO_HVAC_ACTION = {
    "ProducingHeat": HVACAction.HEATING,
    "RequestingHeat": HVACAction.HEATING,
    "Idle": HVACAction.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the Remeha Home climate entity from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            entities.append(RemehaHomeClimateEntity(api, coordinator, climate_zone_id))

    async_add_entities(entities)


class RemehaHomeClimateEntity(CoordinatorEntity, ClimateEntity):
    """Climate entity representing a Remeha Home climate zone."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.api = api
        self.coordinator = coordinator
        self.climate_zone_id = climate_zone_id

        self._attr_unique_id = "_".join([DOMAIN, self.climate_zone_id])

    @property
    def _data(self) -> dict:
        """Return the climate zone information from the coordinator."""
        return self.coordinator.get_climate_zone(self.climate_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_climate_zone_device_info(self.climate_zone_id)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._data["roomTemperature"]

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return self._data["setPoint"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._data["setPointMin"]

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._data["setPointMax"]

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._data["name"]

    @property
    def hvac_mode(self) -> HVACMode | str | None:
        """Return hvac target hvac state."""
        mode = self._data["zoneMode"]
        return REMEHA_MODE_TO_HVAC_MODE.get(mode)

    @property
    def hvac_modes(self) -> list[HVACMode] | list[str]:
        """Return the list of available operation modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

    @property
    def hvac_action(self) -> HVACAction | str | None:
        """Return hvac action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        action = self._data["activeComfortDemand"]
        return REMEHA_STATUS_TO_HVAC_ACTION.get(action)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting temperature to %f", temperature)
            if self.hvac_mode == HVACMode.AUTO:
                await self.api.async_set_temporary_override(
                    self.climate_zone_id, temperature
                )
            elif self.hvac_mode == HVACMode.HEAT:
                await self.api.async_set_manual(self.climate_zone_id, temperature)
            elif self.hvac_mode == HVACMode.OFF:
                return

            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode to %s", hvac_mode)

        # Temporarily override the coordinator state until the next poll
        self._data["zoneMode"] = HVAC_MODE_TO_REMEHA_MODE.get(hvac_mode)
        self.async_write_ha_state()

        if hvac_mode == HVACMode.AUTO:
            await self.api.async_set_schedule(self.climate_zone_id, 1)
        elif hvac_mode == HVACMode.HEAT:
            await self.api.async_set_manual(
                self.climate_zone_id, self._data["setPoint"]
            )
        elif hvac_mode == HVACMode.OFF:
            await self.api.async_set_off(self.climate_zone_id)
        else:
            raise NotImplementedError()

        await self.coordinator.async_request_refresh()
