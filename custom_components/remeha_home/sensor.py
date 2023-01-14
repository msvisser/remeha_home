"""Platform for sensor integration."""
from __future__ import annotations
import logging


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import APPLIANCE_SENSOR_TYPES, CLIMATE_ZONE_SENSOR_TYPES, DOMAIN
from .coordinator import RemehaHomeUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup the Remeha Home sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        appliance_name = appliance["houseName"]
        for entity_description in APPLIANCE_SENSOR_TYPES:
            entities.append(
                RemehaHomeApplianceSensor(
                    coordinator, appliance_id, appliance_name, entity_description
                )
            )

        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            zone_name = climate_zone["name"]

            for entity_description in CLIMATE_ZONE_SENSOR_TYPES:
                entities.append(
                    RemehaHomeClimateZoneSensor(
                        coordinator, climate_zone_id, zone_name, entity_description
                    )
                )

    async_add_entities(entities)


class RemehaHomeApplianceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
        appliance_name: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.appliance_id = appliance_id
        self.appliance_name = appliance_name
        self.entity_description = entity_description

        self._attr_unique_id = "_".join(
            [DOMAIN, self.appliance_id, entity_description.key]
        )

    @property
    def _data(self):
        """Return the appliance data for this sensor."""
        return self.coordinator.get_appliance(self.appliance_id)

    @property
    def native_value(self):
        """Return the measurement value for this sensor."""
        value = self._data[self.entity_description.key]

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value).replace(
                tzinfo=dt_util.DEFAULT_TIME_ZONE
            )

        return value

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return f"{self.appliance_name} {self.entity_description.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_appliance_device_info(self.appliance_id)


class RemehaHomeClimateZoneSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        climate_zone: str,
        zone_name: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.climate_zone_id = climate_zone
        self.zone_name = zone_name
        self.entity_description = entity_description

        self._attr_unique_id = "_".join(
            [DOMAIN, self.climate_zone_id, entity_description.key]
        )

    @property
    def _data(self):
        """Return the climate zone data for this sensor."""
        return self.coordinator.get_climate_zone(self.climate_zone_id)

    @property
    def native_value(self):
        """Return the measurement value for this sensor."""
        value = self._data[self.entity_description.key]

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value).replace(
                tzinfo=dt_util.DEFAULT_TIME_ZONE
            )

        return value

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return f"{self.zone_name} {self.entity_description.name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_climate_zone_device_info(self.climate_zone_id)
