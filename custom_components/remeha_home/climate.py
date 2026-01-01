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


def get_remeha_mode_to_hvac_mode(appliance_type: str) -> dict:
    """Get the mapping from Remeha mode to HVAC mode based on appliance type."""
    if appliance_type == "HeatPump":
        return {
            "Scheduling": HVACMode.AUTO,
            "TemporaryOverride": HVACMode.AUTO,
            "Manual": HVACMode.HEAT_COOL,
            "FrostProtection": HVACMode.OFF,
        }
    else:
        return {
            "Scheduling": HVACMode.AUTO,
            "TemporaryOverride": HVACMode.AUTO,
            "Manual": HVACMode.HEAT,
            "FrostProtection": HVACMode.OFF,
        }


def get_hvac_mode_to_remeha_mode(appliance_type: str) -> dict:
    """Get the mapping from HVAC mode to Remeha mode based on appliance type."""
    if appliance_type == "HeatPump":
        return {
            HVACMode.AUTO: "Scheduling",
            HVACMode.HEAT_COOL: "Manual",
            HVACMode.OFF: "FrostProtection",
        }
    else:
        return {
            HVACMode.AUTO: "Scheduling",
            HVACMode.HEAT: "Manual",
            HVACMode.OFF: "FrostProtection",
        }


REMEHA_STATUS_TO_HVAC_ACTION = {
    "ProducingHeat": HVACAction.HEATING,
    "RequestingHeat": HVACAction.HEATING,
    "ProducingCold": HVACAction.COOLING,
    "RequestingCold": HVACAction.COOLING,
    "Idle": HVACAction.IDLE,
}

PRESET_INDEX_TO_PRESET_MODE = {
    1: "clock_program_1",
    2: "clock_program_2",
    3: "clock_program_3",
}

PRESET_MODE_TO_PRESET_INDEX = {
    "clock_program_1": 1,
    "clock_program_2": 2,
    "clock_program_3": 3,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Remeha Home climate entity from a config entry."""
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

    _enable_turn_on_off_backwards_compatibility = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "remeha_home"

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone_id: str,
    ) -> None:
        """Create a Remeha Home climate entity."""
        super().__init__(coordinator)
        self.api = api
        self.coordinator: RemehaHomeUpdateCoordinator = coordinator
        self.climate_zone_id = climate_zone_id

        self._attr_unique_id = "_".join([DOMAIN, self.climate_zone_id])

    @property
    def _data(self) -> dict:
        """Return the climate zone information from the coordinator."""
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)

    def _get_appliance_data(self) -> dict | None:
        """Get the appliance data for this climate zone."""
        for appliance in self.coordinator.data.get("appliances", []):
            for climate_zone in appliance.get("climateZones", []):
                if climate_zone.get("climateZoneId") == self.climate_zone_id:
                    return appliance
        return None

    def _get_appliance_type(self) -> str:
        """Get the appliance type for this climate zone."""
        appliance_data = self._get_appliance_data()
        return (
            appliance_data.get("applianceType", "Boiler")
            if appliance_data
            else "Boiler"
        )

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
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac target hvac state."""
        mode = self._data["zoneMode"]
        appliance_type = self._get_appliance_type()
        hvac_mode = get_remeha_mode_to_hvac_mode(appliance_type).get(mode)

        # Enhanced debugging for cooling functionality
        _LOGGER.info(
            "🔧 COOLING DEBUG - Zone %s: zoneMode=%s, appliance_type=%s, mapped_hvac_mode=%s",
            self.climate_zone_id,
            mode,
            appliance_type,
            hvac_mode,
        )

        return hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        appliance_type = self._get_appliance_type()
        modes = [HVACMode.OFF, HVACMode.AUTO]

        if appliance_type == "HeatPump":
            # Heat pumps support both heating and cooling
            modes.append(HVACMode.HEAT_COOL)
        else:
            # Regular boilers only support heating
            modes.append(HVACMode.HEAT)

        return modes

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return hvac action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        action = self._data["activeComfortDemand"]
        hvac_action = REMEHA_STATUS_TO_HVAC_ACTION.get(action)

        # Enhanced debugging for cooling functionality
        _LOGGER.info(
            "🔧 COOLING DEBUG - Zone %s: activeComfortDemand=%s, mapped_hvac_action=%s",
            self.climate_zone_id,
            action,
            hvac_action,
        )

        return hvac_action

    @property
    def preset_mode(self) -> str | None:
        """Return the preset mode."""
        if self.hvac_mode == HVACMode.OFF:
            return "anti_frost"
        if self.hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            return "manual"
        return PRESET_INDEX_TO_PRESET_MODE[
            self._data["activeHeatingClimateTimeProgramNumber"]
        ]

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available presets."""
        return list(PRESET_INDEX_TO_PRESET_MODE.values())

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting temperature to %f", temperature)
            if self.hvac_mode == HVACMode.AUTO:
                await self.api.async_set_temporary_override(
                    self.climate_zone_id, temperature
                )
            elif self.hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
                await self.api.async_set_manual(self.climate_zone_id, temperature)
            elif self.hvac_mode == HVACMode.OFF:
                return

            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode to %s", hvac_mode)

        # Temporarily override the coordinator state until the next poll
        appliance_type = self._get_appliance_type()
        hvac_mode_mapping = get_hvac_mode_to_remeha_mode(appliance_type)
        self._data["zoneMode"] = hvac_mode_mapping.get(hvac_mode)
        self.async_write_ha_state()

        if hvac_mode == HVACMode.AUTO:
            await self.api.async_set_schedule(
                self.climate_zone_id,
                self._data["activeHeatingClimateTimeProgramNumber"],
            )
        elif hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            await self.api.async_set_manual(
                self.climate_zone_id, self._data["setPoint"]
            )
        elif hvac_mode == HVACMode.OFF:
            await self.api.async_set_off(self.climate_zone_id)
        else:
            raise NotImplementedError()

        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Setting preset mode to %s", preset_mode)

        if preset_mode not in PRESET_MODE_TO_PRESET_INDEX:
            _LOGGER.error("Trying to set unknown preset mode %s", preset_mode)
            return

        target_preset = PRESET_MODE_TO_PRESET_INDEX[preset_mode]
        previous_hvac_mode = self.hvac_mode

        appliance_type = self._get_appliance_type()
        hvac_mode_mapping = get_hvac_mode_to_remeha_mode(appliance_type)
        self._data["zoneMode"] = hvac_mode_mapping.get(HVACMode.AUTO)
        self._data["activeHeatingClimateTimeProgramNumber"] = target_preset
        self.async_write_ha_state()

        # Switch the selected heating time program
        await self.api.async_activate_heating_time_program(
            self.climate_zone_id, target_preset
        )
        # Automatically make sure the mode is set to schedule
        if previous_hvac_mode != HVACMode.AUTO:
            await self.api.async_set_schedule(self.climate_zone_id, target_preset)

        await self.coordinator.async_request_refresh()
