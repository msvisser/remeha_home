"""Platform for Remeha Home climate integration."""

from __future__ import annotations
from datetime import timedelta
from typing import Any
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .api import RemehaHomeAPI
from .const import (
    DOMAIN,
    PRESET_ANTI_FROST,
    PRESET_INDEX_TO_PRESET_MODE,
    PRESET_MANUAL,
    PRESET_MODE_TO_PRESET_INDEX,
)
from .coordinator import RemehaHomeUpdateCoordinator
from .util import remeha_utc_time

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_TEMPORARY_OVERRIDE = "set_temporary_override"
ATTR_DURATION = "duration"
# The Remeha API doesn't document a limit; one week is a reasonable maximum
MIN_OVERRIDE_DURATION = timedelta(minutes=1)
MAX_OVERRIDE_DURATION = timedelta(days=7)


def manual_hvac_mode(can_cool: bool) -> HVACMode:
    """Return the HVAC mode of the Remeha manual mode.

    Remeha has one manual mode for heating and cooling, so it is heat/cool for a zone
    that can cool, and heat for any other zone.
    """
    return HVACMode.HEAT_COOL if can_cool else HVACMode.HEAT


def get_remeha_mode_to_hvac_mode(can_cool: bool) -> dict:
    """Get the mapping from Remeha mode to HVAC mode."""
    return {
        "Scheduling": HVACMode.AUTO,
        "TemporaryOverride": HVACMode.AUTO,
        "Manual": manual_hvac_mode(can_cool),
        "FrostProtection": HVACMode.OFF,
    }


def get_hvac_mode_to_remeha_mode(can_cool: bool) -> dict:
    """Get the mapping from HVAC mode to Remeha mode."""
    return {
        HVACMode.AUTO: "Scheduling",
        manual_hvac_mode(can_cool): "Manual",
        HVACMode.OFF: "FrostProtection",
    }


REMEHA_STATUS_TO_HVAC_ACTION = {
    "ProducingHeat": HVACAction.HEATING,
    "RequestingHeat": HVACAction.HEATING,
    "ProducingCold": HVACAction.COOLING,
    "RequestingCold": HVACAction.COOLING,
    "Idle": HVACAction.IDLE,
}


def map_remeha_status_to_hvac_action(status: str | None) -> HVACAction | None:
    """Map the raw comfort demand status to a Home Assistant HVAC action."""
    if status is None:
        return None

    if action := REMEHA_STATUS_TO_HVAC_ACTION.get(status):
        return action

    if "Heat" in status:
        return HVACAction.HEATING

    _LOGGER.debug("Unknown comfort demand status received: %s", status)
    return None


# Home Assistant 2026.11 gave climate and water heater entities native temperature
# members (native_temperature_unit, native_current_temperature and
# native_target_temperature) and deprecated the old names until 2027.11. Earlier
# versions only know the old names, so the entities use whichever this version has.
NATIVE_TEMPERATURE_MEMBERS = hasattr(ClimateEntity, "native_temperature_unit")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Remeha Home climate entity from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_TEMPORARY_OVERRIDE,
        {
            vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
            vol.Required(ATTR_DURATION): vol.All(
                cv.time_period,
                vol.Range(min=MIN_OVERRIDE_DURATION, max=MAX_OVERRIDE_DURATION),
            ),
        },
        "async_set_temporary_override",
    )

    entities = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            entities.append(RemehaHomeClimateEntity(api, coordinator, climate_zone_id))

    async_add_entities(entities)


class RemehaHomeClimateEntity(CoordinatorEntity, ClimateEntity):
    """Climate entity representing a Remeha Home climate zone."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    if NATIVE_TEMPERATURE_MEMBERS:
        _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    else:
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
        # Whether the zone has a Cooling activity, None until the activities are known
        self._has_cooling_activity: bool | None = None

        self._attr_unique_id = "_".join([DOMAIN, self.climate_zone_id])

    @property
    def _data(self) -> dict:
        """Return the climate zone information from the coordinator."""
        return self.coordinator.get_by_id(self.climate_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.climate_zone_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the end of a temporary override, None when there is none."""
        end = remeha_utc_time(
            (self._data.get("temporaryOverride") or {}).get("endTime")
        )
        return {"override_end_time": dt_util.as_local(end).isoformat() if end else None}

    def _get_appliance_data(self) -> dict | None:
        """Get the appliance data for this climate zone."""
        for appliance in self.coordinator.data.get("appliances", []):
            for climate_zone in appliance.get("climateZones", []):
                if climate_zone.get("climateZoneId") == self.climate_zone_id:
                    return appliance
        return None

    def _can_cool(self) -> bool:
        """Return whether this climate zone can cool.

        A zone can cool when it reports capabilityCooling true (the zone's value
        first, else the appliance's) or when it has a Cooling activity: a system that
        cools can still report capabilityCooling false, but it has Cooling activities.

        The activities are fetched once and again after an activity is changed, so
        they can be missing for a moment; the last result is kept meanwhile, so the
        modes don't flip. Before they have ever been fetched, a heat pump is assumed
        to cool.
        """
        appliance_data = self._get_appliance_data() or {}
        capability = self._data.get("capabilityCooling")
        if capability is None:
            capability = appliance_data.get("capabilityCooling")
        if capability:
            return True

        activities = self.coordinator.get_activities(self.climate_zone_id)
        if activities is not None:
            self._has_cooling_activity = any(
                activity.get("type") == "Cooling" for activity in activities
            )
        if self._has_cooling_activity is not None:
            return self._has_cooling_activity

        return appliance_data.get("applianceType") == "HeatPump"

    def _room_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._data["roomTemperature"]

    def _setpoint(self) -> float | None:
        """Return the target temperature."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return self._data["setPoint"]

    if NATIVE_TEMPERATURE_MEMBERS:
        native_current_temperature = property(_room_temperature)
        native_target_temperature = property(_setpoint)
    else:
        current_temperature = property(_room_temperature)
        target_temperature = property(_setpoint)

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
        return get_remeha_mode_to_hvac_mode(self._can_cool()).get(mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available operation modes."""
        return [HVACMode.OFF, HVACMode.AUTO, manual_hvac_mode(self._can_cool())]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return hvac action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        return map_remeha_status_to_hvac_action(self._data.get("activeComfortDemand"))

    @property
    def preset_mode(self) -> str | None:
        """Return the preset mode."""
        if self.hvac_mode == HVACMode.OFF:
            return PRESET_ANTI_FROST
        if self.hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            return PRESET_MANUAL
        return PRESET_INDEX_TO_PRESET_MODE[
            self._data["activeHeatingClimateTimeProgramNumber"]
        ]

    @property
    def preset_modes(self) -> list[str]:
        """Return the list of available presets: the clock programs, manual and off."""
        return [
            *PRESET_INDEX_TO_PRESET_MODE.values(),
            PRESET_MANUAL,
            PRESET_ANTI_FROST,
        ]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature, optionally together with a new operation mode."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        requested_hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if temperature is None:
            if requested_hvac_mode is not None:
                await self.async_set_hvac_mode(requested_hvac_mode)
            return

        current_hvac_mode = self.hvac_mode
        hvac_mode = requested_hvac_mode or current_hvac_mode
        _LOGGER.debug("Setting temperature to %f in mode %s", temperature, hvac_mode)

        if hvac_mode == HVACMode.OFF:
            # The setpoint can't be stored while the zone is in frost protection,
            # so fail loudly instead of silently dropping it
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_temperature_while_off",
            )

        if hvac_mode == HVACMode.AUTO:
            if current_hvac_mode != HVACMode.AUTO:
                await self.api.async_set_schedule(
                    self.climate_zone_id,
                    self._data["activeHeatingClimateTimeProgramNumber"],
                )
            await self.api.async_set_temporary_override(
                self.climate_zone_id, temperature
            )
        elif hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            # Switches the zone to manual mode with the new setpoint in one request
            await self.api.async_set_manual(self.climate_zone_id, temperature)
        else:
            raise NotImplementedError()

        await self.coordinator.async_request_refresh()

    async def async_set_temporary_override(
        self, temperature: float, duration: timedelta
    ) -> None:
        """Override the clock program with a temperature for a while.

        The appliance ends the override by itself at the end time, also when Home
        Assistant isn't running, and returns to the clock program.
        """
        if self._data.get("capabilityTemporaryOverrideEndTime") is not True:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temporary_override_not_supported",
                translation_placeholders={"entity_id": self.entity_id},
            )
        if self.hvac_mode != HVACMode.AUTO:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temporary_override_requires_auto",
                translation_placeholders={"entity_id": self.entity_id},
            )
        if not self.min_temp <= temperature <= self.max_temp:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="temperature_out_of_range",
                translation_placeholders={
                    "temperature": str(temperature),
                    "min_temp": str(self.min_temp),
                    "max_temp": str(self.max_temp),
                },
            )

        end_time = (dt_util.utcnow() + duration).replace(microsecond=0)
        _LOGGER.debug("Setting temperature to %f until %s", temperature, end_time)
        await self.api.async_set_temporary_override(
            self.climate_zone_id, temperature, end_time
        )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode to %s", hvac_mode)

        # Temporarily override the coordinator state until the next poll
        hvac_mode_mapping = get_hvac_mode_to_remeha_mode(self._can_cool())
        zone_data = self._data
        previous_zone_mode = zone_data["zoneMode"]
        zone_data["zoneMode"] = hvac_mode_mapping.get(hvac_mode)
        self.async_write_ha_state()

        try:
            if hvac_mode == HVACMode.AUTO:
                await self.api.async_set_schedule(
                    self.climate_zone_id,
                    zone_data["activeHeatingClimateTimeProgramNumber"],
                )
            elif hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
                await self.api.async_set_manual(
                    self.climate_zone_id, zone_data["setPoint"]
                )
            elif hvac_mode == HVACMode.OFF:
                await self.api.async_set_off(self.climate_zone_id)
            else:
                raise NotImplementedError()
        except Exception:
            # Revert the temporary override, the zone did not change
            zone_data["zoneMode"] = previous_zone_mode
            self.async_write_ha_state()
            raise

        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Setting preset mode to %s", preset_mode)

        # Manual and frost protection are the heat (or heat/cool) and off modes
        if preset_mode == PRESET_MANUAL:
            await self.async_set_hvac_mode(manual_hvac_mode(self._can_cool()))
            return
        if preset_mode == PRESET_ANTI_FROST:
            await self.async_set_hvac_mode(HVACMode.OFF)
            return

        if preset_mode not in PRESET_MODE_TO_PRESET_INDEX:
            _LOGGER.error("Trying to set unknown preset mode %s", preset_mode)
            return

        target_preset = PRESET_MODE_TO_PRESET_INDEX[preset_mode]
        previous_hvac_mode = self.hvac_mode

        hvac_mode_mapping = get_hvac_mode_to_remeha_mode(self._can_cool())
        zone_data = self._data
        previous_zone_mode = zone_data["zoneMode"]
        previous_preset = zone_data["activeHeatingClimateTimeProgramNumber"]
        zone_data["zoneMode"] = hvac_mode_mapping.get(HVACMode.AUTO)
        zone_data["activeHeatingClimateTimeProgramNumber"] = target_preset
        self.async_write_ha_state()

        try:
            # Switch the selected heating time program
            await self.api.async_activate_heating_time_program(
                self.climate_zone_id, target_preset
            )
            # Automatically make sure the mode is set to schedule
            if previous_hvac_mode != HVACMode.AUTO:
                await self.api.async_set_schedule(self.climate_zone_id, target_preset)
        except Exception:
            # Revert the temporary override. If only the schedule request failed,
            # the next poll picks up the program that was already activated.
            zone_data["zoneMode"] = previous_zone_mode
            zone_data["activeHeatingClimateTimeProgramNumber"] = previous_preset
            self.async_write_ha_state()
            raise

        await self.coordinator.async_request_refresh()
