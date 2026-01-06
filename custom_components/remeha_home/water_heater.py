"""Platform for DHW control."""

from __future__ import annotations
from typing import Any

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
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
from .util import detect_dhw_setpoint_activity

REMEHA_DHW_MODE_TO_OPERATION = {
    "ContinuousComfort": STATE_PERFORMANCE,
    "Scheduling": STATE_HEAT_PUMP,
    "Off": STATE_ECO,
    "Boost": STATE_HIGH_DEMAND,
}

OPERATION_TO_REMEHA_DHW_MODE = {
    STATE_PERFORMANCE: "ContinuousComfort",
    STATE_HEAT_PUMP: "Scheduling",
    STATE_ECO: "Off",
    STATE_HIGH_DEMAND: "Boost",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DHW water heater entities from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        for hot_water_zone in appliance["hotWaterZones"]:
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            entities.append(
                RemehaHomeWaterHeater(api, coordinator, appliance_id, hot_water_zone_id)
            )

    async_add_entities(entities)


class RemehaHomeWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Water heater entity representing a DHW zone."""

    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "remeha_home_dhw"
    _attr_has_entity_name = True
    _attr_name = None
    _attr_precision = PRECISION_HALVES

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
        hot_water_zone_id: str,
    ) -> None:
        """Create a DHW water heater entity."""
        super().__init__(coordinator)
        self.api = api
        self.appliance_id = appliance_id
        self.hot_water_zone_id = hot_water_zone_id
        self._attr_unique_id = "_".join([DOMAIN, self.hot_water_zone_id, "water_heater"])

    @property
    def _data(self) -> dict:
        """Return the DHW zone information."""
        return self.coordinator.get_by_id(self.hot_water_zone_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.hot_water_zone_id)

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        return REMEHA_DHW_MODE_TO_OPERATION.get(self._data.get("dhwZoneMode"))

    @property
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        return [STATE_HEAT_PUMP, STATE_PERFORMANCE, STATE_ECO, STATE_HIGH_DEMAND]

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature based on the active setpoint."""
        setpoint_type = self._current_setpoint_type()
        if setpoint_type == "comfort":
            return self._data.get("comfortSetPoint")
        if setpoint_type == "eco":
            return self._data.get("reducedSetpoint")
        return self._data.get("targetSetpoint")

    @property
    def current_temperature(self) -> float | None:
        """Return the current DHW temperature."""
        return self._data.get("dhwTemperature")

    @property
    def min_temp(self) -> float | None:
        """Return the minimum setpoint for the active setpoint type."""
        ranges = self._data.get("setPointRanges") or {}
        active = self._current_setpoint_type()
        if active == "comfort":
            return ranges.get("comfortSetpointMin", self._data.get("setPointMin"))
        return ranges.get("reducedSetpointMin", self._data.get("setPointMin"))

    @property
    def max_temp(self) -> float | None:
        """Return the maximum setpoint for the active setpoint type."""
        ranges = self._data.get("setPointRanges") or {}
        active = self._current_setpoint_type()
        if active == "comfort":
            return ranges.get("comfortSetpointMax", self._data.get("setPointMax"))
        return ranges.get("reducedSetpointMax", self._data.get("setPointMax"))

    def _current_setpoint_type(self) -> str:
        """Return the active setpoint type based on the current mode."""
        mode = self._data.get("dhwZoneMode")
        if mode in ("ContinuousComfort", "Boost"):
            return "comfort"
        if mode == "Off":
            return "eco"
        if mode == "Scheduling":
            activity = self._data.get("dhwCurrentActivity")
            if activity == "Comfort":
                return "comfort"
            if activity == "Eco":
                return "eco"
            return "eco"
        return "eco"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes for diagnostics."""
        return {
            "dhw_status": self._data.get("dhwStatus"),
            "boost_mode_end_time": self._data.get("boostModeEndTime"),
            "heating_state": self._heating_state(),
        }

    def _heating_state(self) -> str | None:
        """Return an auxiliary heating state."""
        dhw_status = self._data.get("dhwStatus")
        if dhw_status in ("ProducingHeat", "RequestingHeat"):
            return STATE_HIGH_DEMAND
        if dhw_status == "LowTemperature":
            return "low_temperature"
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature for the active setpoint."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        setpoint_type = self._current_setpoint_type()
        if setpoint_type == "comfort":
            # Optimistic local update to avoid transient UI mismatches
            self._data["comfortSetPoint"] = temperature
            self._data["targetSetpoint"] = temperature
            await self.api.async_set_dhw_comfort_setpoint(
                self.hot_water_zone_id, temperature
            )
        else:
            self._data["reducedSetpoint"] = temperature
            self._data["targetSetpoint"] = temperature
            await self.api.async_set_dhw_reduced_setpoint(
                self.hot_water_zone_id, temperature
            )

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set operation mode."""
        target_mode = OPERATION_TO_REMEHA_DHW_MODE.get(operation_mode)
        if not target_mode:
            return

        if target_mode == "ContinuousComfort":
            await self.api.async_set_dhw_mode_comfort(self.hot_water_zone_id)
        elif target_mode == "Scheduling":
            await self.api.async_set_dhw_mode_schedule(self.hot_water_zone_id)
        elif target_mode == "Off":
            await self.api.async_set_dhw_mode_eco(self.hot_water_zone_id)
        elif target_mode == "Boost":
            duration = self._data.get("boostDuration") or 30
            await self.api.async_set_hot_water_boost(self.hot_water_zone_id, True, duration)
        else:
            return

        # Optimistic update until the coordinator polls fresh data
        self._data["dhwZoneMode"] = target_mode
        self._set_optimistic_target_setpoint(target_mode)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_optimistic_target_setpoint(self, target_mode: str) -> None:
        """Update local target setpoint to reflect the selected mode immediately."""
        if target_mode in ("ContinuousComfort", "Boost"):
            self._data["targetSetpoint"] = self._data.get("comfortSetPoint")
            return
        if target_mode == "Scheduling":
            activity = detect_dhw_setpoint_activity(
                self._data.get("targetSetpoint"),
                self._data.get("comfortSetPoint"),
                self._data.get("reducedSetpoint"),
            )
            if activity == "Comfort":
                self._data["targetSetpoint"] = self._data.get("comfortSetPoint")
            elif activity == "Eco":
                self._data["targetSetpoint"] = self._data.get("reducedSetpoint")
            return
        if target_mode == "Off":
            self._data["targetSetpoint"] = self._data.get("reducedSetpoint")
