"""Platform for DHW setpoint numbers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RemehaHomeAPI
from .const import DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up DHW numbers from a config entry."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[RemehaHomeDhwSetpointNumber] = []
    for appliance in coordinator.data["appliances"]:
        for hot_water_zone in appliance["hotWaterZones"]:
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            entities.append(
                RemehaHomeDhwSetpointNumber(
                    api,
                    coordinator,
                    hot_water_zone_id,
                    setpoint_type="comfort",
                    name="Comfort Temperature",
                    key="comfortSetPoint",
                    icon="mdi:water-thermometer",
                )
            )
            entities.append(
                RemehaHomeDhwSetpointNumber(
                    api,
                    coordinator,
                    hot_water_zone_id,
                    setpoint_type="eco",
                    name="Eco Temperature",
                    key="reducedSetpoint",
                    icon="mdi:water-thermometer-outline",
                )
            )

    async_add_entities(entities)


class RemehaHomeDhwSetpointNumber(CoordinatorEntity, NumberEntity):
    """Number entity for DHW setpoints."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = PRECISION_HALVES

    def __init__(
        self,
        api: RemehaHomeAPI,
        coordinator: RemehaHomeUpdateCoordinator,
        hot_water_zone_id: str,
        *,
        setpoint_type: str,
        name: str,
        key: str,
        icon: str,
    ) -> None:
        """Create a DHW setpoint number."""
        super().__init__(coordinator)
        self.api = api
        self.hot_water_zone_id = hot_water_zone_id
        self.setpoint_type = setpoint_type
        self._attr_name = name
        self.key = key
        self._attr_unique_id = "_".join([DOMAIN, self.hot_water_zone_id, key])
        self._attr_icon = icon

    @property
    def _data(self):
        """Return zone data."""
        return self.coordinator.get_by_id(self.hot_water_zone_id)

    @property
    def native_value(self) -> float | None:
        """Return current setpoint value."""
        return self._data.get(self.key)

    @property
    def native_min_value(self) -> float | None:
        """Return minimum allowed value for this setpoint."""
        ranges = self._data.get("setPointRanges") or {}
        if self.setpoint_type == "comfort":
            return ranges.get("comfortSetpointMin", self._data.get("setPointMin"))
        return ranges.get("reducedSetpointMin", self._data.get("setPointMin"))

    @property
    def native_max_value(self) -> float | None:
        """Return maximum allowed value for this setpoint."""
        ranges = self._data.get("setPointRanges") or {}
        if self.setpoint_type == "comfort":
            return ranges.get("comfortSetpointMax", self._data.get("setPointMax"))
        return ranges.get("reducedSetpointMax", self._data.get("setPointMax"))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.hot_water_zone_id)

    async def async_set_native_value(self, value: float) -> None:
        """Update the setpoint."""
        if self.setpoint_type == "comfort":
            await self.api.async_set_dhw_comfort_setpoint(
                self.hot_water_zone_id, value
            )
        else:
            await self.api.async_set_dhw_reduced_setpoint(
                self.hot_water_zone_id, value
            )

        await self.coordinator.async_request_refresh()
