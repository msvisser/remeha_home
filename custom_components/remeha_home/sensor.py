"""Platform for sensor integration."""

from __future__ import annotations
import logging


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    APPLIANCE_SENSOR_TYPES,
    CLIMATE_ZONE_SENSOR_TYPES,
    DOMAIN,
    HOT_WATER_ZONE_SENSOR_TYPES,
)
from .coordinator import RemehaHomeUpdateCoordinator
from .util import remeha_time

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        for entity_description in APPLIANCE_SENSOR_TYPES:
            entities.append(
                RemehaHomeSensor(coordinator, appliance_id, entity_description)
            )

        # Per producer (heat pump, gas boiler) of a hybrid appliance, from the
        # daily consumption data the coordinator already fetches
        producers = (
            (
                (appliance.get("consumptionData") or {}).get(
                    "producerPerformanceStatistics"
                )
                or {}
            ).get("producers")
        ) or []
        for producer in producers:
            for field, entity_description in PRODUCER_SENSOR_FIELDS:
                entities.append(
                    RemehaHomeProducerSensor(
                        coordinator,
                        appliance_id,
                        producer.get("instanceWithinDevice"),
                        producer.get("producerType") or "Producer",
                        field,
                        entity_description,
                    )
                )

        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            for entity_description in CLIMATE_ZONE_SENSOR_TYPES:
                entities.append(
                    RemehaHomeSensor(coordinator, climate_zone_id, entity_description)
                )

        for hot_water_zone in appliance["hotWaterZones"]:
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            for entity_description in HOT_WATER_ZONE_SENSOR_TYPES:
                # Combi appliances report no hot water temperature (always null);
                # don't create a sensor that can only ever read unknown
                if (
                    entity_description.key == "dhwTemperature"
                    and hot_water_zone.get("dhwTemperature") is None
                ):
                    continue
                entities.append(
                    RemehaHomeSensor(coordinator, hot_water_zone_id, entity_description)
                )

    async_add_entities(entities)


class RemehaHomeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        item_id: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Create a Remeha Home sensor entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.item_id = item_id
        self._attr_unique_id = "_".join([DOMAIN, self.item_id, entity_description.key])

    @property
    def _data(self):
        """Return the appliance data for this sensor."""
        return self.coordinator.get_by_id(self.item_id)

    @property
    def native_value(self):
        """Return the measurement value for this sensor."""
        data = self._data
        for part in self.entity_description.key.split("."):
            # If the key is missing for some reason, don't crash, instead return None
            if part not in data:
                _LOGGER.warning(
                    "Key not found in data: %s", self.entity_description.key
                )
                return None
            data = data[part]
        value = data

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return remeha_time(value)

        return value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.item_id)


PRODUCER_NAMES = {
    "HeatPumpAirSource": "Heat Pump",
    "HeatPumpGroundSource": "Heat Pump",
    "GasBoiler": "Gas Boiler",
}

PRODUCER_SENSOR_FIELDS = [
    (
        "energyConsumptionTotal",
        SensorEntityDescription(
            key="energy_consumed",
            name="Energy Consumed",
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    (
        "energyProductionTotal",
        SensorEntityDescription(
            key="energy_delivered",
            name="Energy Delivered",
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    (
        "seasonalEfficiency",
        SensorEntityDescription(
            key="efficiency",
            name="Efficiency",
            icon="mdi:gauge",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
]


class RemehaHomeProducerSensor(CoordinatorEntity, SensorEntity):
    """Daily energy figure of one producer (heat pump or boiler) of an appliance.

    Like the appliance energy sensors, the values are today's totals and reset
    at midnight.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RemehaHomeUpdateCoordinator,
        appliance_id: str,
        instance: int | None,
        producer_type: str,
        field: str,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Create a Remeha Home producer sensor entity."""
        super().__init__(coordinator)
        self.appliance_id = appliance_id
        self.instance = instance
        self.producer_type = producer_type
        self.field = field
        self.entity_description = entity_description
        prefix = PRODUCER_NAMES.get(producer_type, producer_type)
        self._attr_name = f"{prefix} {entity_description.name}"
        self._attr_unique_id = "_".join(
            [DOMAIN, appliance_id, f"producer{instance}", entity_description.key]
        )

    def _producer(self) -> dict | None:
        appliance = self.coordinator.get_by_id(self.appliance_id) or {}
        producers = (
            (
                (appliance.get("consumptionData") or {}).get(
                    "producerPerformanceStatistics"
                )
                or {}
            ).get("producers")
        ) or []
        for producer in producers:
            if (
                producer.get("instanceWithinDevice") == self.instance
                and producer.get("producerType") == self.producer_type
            ):
                return producer
        return None

    @property
    def native_value(self):
        """Return today's value, or None when the producer reports none."""
        producer = self._producer()
        if producer is None:
            return None
        return producer.get(self.field)

    @property
    def extra_state_attributes(self):
        """Return the energy type of the producer."""
        producer = self._producer() or {}
        return {"energy_type": producer.get("energyType")}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.appliance_id)
