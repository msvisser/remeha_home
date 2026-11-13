"""Platform for binary sensor integration."""

from __future__ import annotations
import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import voluptuous as vol


from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import RemehaHomeAPI
from .const import (
    DOMAIN,
    APPLIANCE_BINARY_SENSOR_TYPES,
    CLIMATE_ZONE_BINARY_SENSOR_TYPES,
    HOT_WATER_ZONE_BINARY_SENSOR_TYPES,
    HOT_WATER_ZONE_OPTIMIZATION_BINARY_SENSOR_TYPES,
)
from .coordinator import RemehaHomeUpdateCoordinator
from .util import remeha_time, reports_water_pressure

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_HOLIDAY_MODE = "set_holiday_mode"
SERVICE_CANCEL_HOLIDAY_MODE = "cancel_holiday_mode"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

WATER_PRESSURE_OK = "waterPressureOK"

# The API applies changes a few seconds after the request
REFRESH_DELAY = 15


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_HOLIDAY_MODE,
        {
            vol.Required(ATTR_START_DATE): cv.date,
            vol.Required(ATTR_END_DATE): cv.date,
        },
        _async_handle_holiday_service,
    )
    platform.async_register_entity_service(
        SERVICE_CANCEL_HOLIDAY_MODE, {}, _async_handle_holiday_service
    )

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        entities.append(
            RemehaHomeHolidayModeBinarySensor(coordinator, api, appliance_id)
        )
        appliance_types = APPLIANCE_BINARY_SENSOR_TYPES
        if not reports_water_pressure(appliance):
            # Without a pressure the problem sensor would show a problem that isn't
            # there, also remove the one created before
            appliance_types = [
                (description, transform)
                for description, transform in appliance_types
                if description.key != WATER_PRESSURE_OK
            ]
            _async_remove_binary_sensor(hass, appliance_id, WATER_PRESSURE_OK)
        entities.extend(
            _binary_sensors(coordinator, appliance, appliance_id, appliance_types)
        )

        for climate_zone in appliance["climateZones"]:
            entities.extend(
                _binary_sensors(
                    coordinator,
                    climate_zone,
                    climate_zone["climateZoneId"],
                    CLIMATE_ZONE_BINARY_SENSOR_TYPES,
                )
            )

        hot_water_zone_types = HOT_WATER_ZONE_BINARY_SENSOR_TYPES
        if appliance.get("capabilityDhwOptimization"):
            hot_water_zone_types = (
                hot_water_zone_types + HOT_WATER_ZONE_OPTIMIZATION_BINARY_SENSOR_TYPES
            )

        for hot_water_zone in appliance["hotWaterZones"]:
            entities.extend(
                _binary_sensors(
                    coordinator,
                    hot_water_zone,
                    hot_water_zone["hotWaterZoneId"],
                    hot_water_zone_types,
                )
            )

    async_add_entities(entities)


def _async_remove_binary_sensor(hass: HomeAssistant, item_id: str, key: str) -> None:
    """Remove a binary sensor that is no longer created from the entity registry."""
    entity_registry = er.async_get(hass)
    unique_id = "_".join([DOMAIN, item_id, key])
    if entity_id := entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, unique_id
    ):
        entity_registry.async_remove(entity_id)


def _lookup(data: dict | None, key: str) -> tuple[bool, Any]:
    """Return whether the data has the (dotted) key, and its value."""
    for part in key.split("."):
        if not isinstance(data, dict) or part not in data:
            return False, None
        data = data[part]
    return True, data


def _binary_sensors(
    coordinator: RemehaHomeUpdateCoordinator,
    data: dict,
    item_id: str,
    sensor_types: list,
) -> list[RemehaHomeBinarySensor]:
    """Return the binary sensors of an item, for the values that it reports."""
    return [
        RemehaHomeBinarySensor(coordinator, item_id, entity_description, transform_func)
        for entity_description, transform_func in sensor_types
        if _lookup(data, entity_description.key)[0]
    ]


class RemehaHomeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        item_id: str,
        entity_description: BinarySensorEntityDescription,
        transform_func: Callable[[str], bool],
    ) -> None:
        """Create a Remeha Home binary sensor entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.transform_func = transform_func
        self.item_id = item_id
        self._attr_unique_id = "_".join([DOMAIN, self.item_id, entity_description.key])

    @property
    def _data(self):
        """Return the appliance data for this sensor."""
        return self.coordinator.get_by_id(self.item_id)

    @property
    def is_on(self) -> bool | None:
        """Return the measurement value for this sensor, or None when not reported."""
        found, value = _lookup(self._data, self.entity_description.key)
        if not found or value is None:
            return None
        if (
            self.entity_description.key == WATER_PRESSURE_OK
            and not reports_water_pressure(self._data)
        ):
            # Without a pressure, waterPressureOK false doesn't mean a problem
            return None

        return self.transform_func(value)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.item_id)


class RemehaHomeHolidayModeBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Holiday mode of an appliance, with services to schedule and cancel it."""

    _attr_has_entity_name = True
    _attr_name = "Holiday Mode"
    _attr_icon = "mdi:beach"

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        api: RemehaHomeAPI,
        appliance_id: str,
    ) -> None:
        """Create a Remeha Home holiday mode binary sensor."""
        super().__init__(coordinator)
        self.api = api
        self.appliance_id = appliance_id
        self._attr_unique_id = "_".join([DOMAIN, appliance_id, "holidaySchedule"])

    @property
    def _schedule(self) -> dict:
        return self.coordinator.get_by_id(self.appliance_id).get("holidaySchedule") or {}

    @property
    def is_on(self) -> bool:
        """Return true while holiday mode is active."""
        return bool(self._schedule.get("active"))

    @property
    def extra_state_attributes(self) -> dict:
        """Return the scheduled holiday period (None when not set)."""
        # The API reports 0001-01-01T00:00:01Z when no holiday is set
        start = remeha_time(self._schedule.get("startTime"))
        end = remeha_time(self._schedule.get("endTime"))
        return {
            ATTR_START_DATE: start.date().isoformat() if start else None,
            ATTR_END_DATE: end.date().isoformat() if end else None,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.appliance_id)

    async def async_set_holiday_mode(self, start_date: date, end_date: date) -> None:
        """Schedule holiday mode from start_date to end_date (whole days)."""
        if end_date <= start_date:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="holiday_end_before_start",
            )
        if end_date <= dt_util.now().date():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="holiday_end_in_past",
            )

        await self.api.async_set_holiday_schedule(self.appliance_id, start_date, end_date)
        await self._async_refresh_soon()

    async def async_cancel_holiday_mode(self) -> None:
        """Cancel holiday mode (active or scheduled)."""
        await self.api.async_cancel_holiday_schedule(self.appliance_id)
        await self._async_refresh_soon()

    async def _async_refresh_soon(self) -> None:
        """Refresh now and again once the API has applied the change."""
        await self.coordinator.async_request_refresh()

        async def _refresh(_now: datetime) -> None:
            await self.coordinator.async_request_refresh()

        self.async_on_remove(async_call_later(self.hass, REFRESH_DELAY, _refresh))


async def _async_handle_holiday_service(entity: Entity, call: ServiceCall) -> None:
    """Run a holiday mode action on the Holiday Mode sensor.

    The actions can target every binary sensor of the integration, so give a clear
    error for the other ones.
    """
    if not isinstance(entity, RemehaHomeHolidayModeBinarySensor):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="holiday_mode_wrong_entity",
            translation_placeholders={"entity_id": entity.entity_id},
        )

    if call.service == SERVICE_SET_HOLIDAY_MODE:
        await entity.async_set_holiday_mode(
            call.data[ATTR_START_DATE], call.data[ATTR_END_DATE]
        )
    else:
        await entity.async_cancel_holiday_mode()
