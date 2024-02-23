"""Platform for binary sensor integration."""
from __future__ import annotations
import logging
from collections.abc import Callable


from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CLIMATE_ZONE_BINARY_SENSOR_TYPES,
    HOT_WATER_ZONE_BINARY_SENSOR_TYPES,
)
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            for (
                entity_description,
                transform_func,
            ) in CLIMATE_ZONE_BINARY_SENSOR_TYPES:
                entities.append(
                    RemehaHomeBinarySensor(
                        coordinator,
                        climate_zone_id,
                        entity_description,
                        transform_func,
                    )
                )

        for hot_water_zone in appliance["hotWaterZones"]:
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            for (
                entity_description,
                transform_func,
            ) in HOT_WATER_ZONE_BINARY_SENSOR_TYPES:
                entities.append(
                    RemehaHomeBinarySensor(
                        coordinator,
                        hot_water_zone_id,
                        entity_description,
                        transform_func,
                    )
                )

    async_add_entities(entities)


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
    def is_on(self) -> bool:
        """Return the measurement value for this sensor."""
        data = self._data
        for part in self.entity_description.key.split("."):
            data = data[part]

        return self.transform_func(data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.item_id)
