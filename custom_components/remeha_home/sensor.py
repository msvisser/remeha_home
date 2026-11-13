"""Platform for sensor integration."""

from __future__ import annotations
import logging
from typing import Any


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    APPLIANCE_SENSOR_TYPES,
    CLIMATE_ZONE_SENSOR_TYPES,
    DOMAIN,
    HEATING_CURVE_SENSOR_TYPES,
    HOT_WATER_ZONE_SENSOR_TYPES,
    GAS_PRODUCER_SENSOR_TYPES,
    ELECTRIC_PRODUCER_SENSOR_TYPES,
    PRESET_INDEX_TO_PRESET_MODE,
)
from .coordinator import (
    PRODUCER_STATS,
    RemehaHomeUpdateCoordinator,
    get_producers,
)
from .schedule import heating_schedule, hot_water_schedule
from .util import (
    remeha_time,
    remeha_utc_time,
    reports_dhw_temperature,
    reports_water_pressure,
)

_LOGGER = logging.getLogger(__name__)

# Times that the API sends in UTC, the other times are local times
UTC_TIME_KEYS = {"temporaryOverride.endTime"}

# Values that the API names differently from the other entities
VALUE_FUNCTIONS = {
    # The API calls Eco "Reduced", after its setpoint. The Mode sensor and the
    # Remeha Home app call it Eco.
    "nextSwitchActivity": lambda value: "Eco" if value == "Reduced" else value,
    # The clock program number, named like the presets of the climate entity. Another
    # value stays as sent, so that it is logged as unexpected.
    "activeDwhTimeProgramNumber": lambda value: PRESET_INDEX_TO_PRESET_MODE.get(
        value, value
    ),
    "activeHeatingClimateTimeProgramNumber": lambda value: (
        PRESET_INDEX_TO_PRESET_MODE.get(value, value)
    ),
}

# Totals per energy type on the appliance, replaced by the sensors of the producer devices
REMOVED_APPLIANCE_SENSOR_KEYS = [
    *(
        f"consumptionData.{stat}{energy_type}"
        for energy_type in ("Electric", "NaturalGas")
        for stat in PRODUCER_STATS
    ),
    "consumptionData.seasonalEfficiencyElectric",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Remeha Home sensor entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for appliance in coordinator.data["appliances"]:
        appliance_id = appliance["applianceId"]
        for entity_description in APPLIANCE_SENSOR_TYPES:
            if entity_description.key == "waterPressure" and not (
                reports_water_pressure(appliance)
            ):
                # It would always be unknown, also remove the one created before
                _async_remove_sensor(hass, appliance_id, entity_description.key)
                continue
            entities.append(
                RemehaHomeSensor(coordinator, appliance_id, entity_description)
            )

        for climate_zone in appliance["climateZones"]:
            climate_zone_id = climate_zone["climateZoneId"]
            for entity_description in CLIMATE_ZONE_SENSOR_TYPES:
                entities.append(
                    _sensor_class(entity_description)(
                        coordinator, climate_zone_id, entity_description
                    )
                )

            heating_curve = coordinator.get_heating_curve(climate_zone_id) or {}
            for entity_description in HEATING_CURVE_SENSOR_TYPES:
                if entity_description.key.split(".")[-1] in heating_curve:
                    entities.append(
                        RemehaHomeSensor(
                            coordinator, climate_zone_id, entity_description
                        )
                    )

        for hot_water_zone in appliance["hotWaterZones"]:
            hot_water_zone_id = hot_water_zone["hotWaterZoneId"]
            for entity_description in HOT_WATER_ZONE_SENSOR_TYPES:
                if entity_description.key == "dhwTemperature" and not (
                    reports_dhw_temperature(hot_water_zone)
                ):
                    # It would always be unknown, also remove the one created before
                    _async_remove_sensor(hass, hot_water_zone_id, entity_description.key)
                    continue
                entities.append(
                    _sensor_class(entity_description)(
                        coordinator, hot_water_zone_id, entity_description
                    )
                )
    async_add_entities(entities)

    _async_remove_replaced_sensors(hass, coordinator)

    known_producer_ids: set[str] = set()

    @callback
    def async_add_producer_sensors() -> None:
        """Add the sensors of producers that were not seen before.

        Right after midnight the API doesn't list the producers until the data for
        the new day is reported, so they can appear after the setup.
        """
        new_entities = []
        for appliance in coordinator.data["appliances"]:
            producers = get_producers(appliance["consumptionData"])
            for producer in producers:
                producer_id = coordinator.producer_id_resolver.get_id(
                    appliance["applianceId"], producer
                )
                if producer_id is None:
                    continue
                if producer_id in known_producer_ids:
                    continue
                known_producer_ids.add(producer_id)

                if producer.get("energyType") == "NaturalGas":
                    entity_descriptions = GAS_PRODUCER_SENSOR_TYPES
                elif producer.get("energyType") == "Electric":
                    entity_descriptions = ELECTRIC_PRODUCER_SENSOR_TYPES
                else:
                    # Unsupported energy sources must not get electrical sensors.
                    continue
                new_entities.extend(
                    RemehaHomeSensor(coordinator, producer_id, entity_description)
                    for entity_description in entity_descriptions
                )

        if new_entities:
            async_add_entities(new_entities)

    async_add_producer_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_add_producer_sensors))


def _async_remove_replaced_sensors(
    hass: HomeAssistant, coordinator: RemehaHomeUpdateCoordinator
) -> None:
    """Remove the totals per energy type, replaced by the producer devices."""
    for appliance in coordinator.data["appliances"]:
        for key in REMOVED_APPLIANCE_SENSOR_KEYS:
            _async_remove_sensor(hass, appliance["applianceId"], key)


def _async_remove_sensor(hass: HomeAssistant, item_id: str, key: str) -> None:
    """Remove a sensor that is no longer created from the entity registry."""
    entity_registry = er.async_get(hass)
    unique_id = "_".join([DOMAIN, item_id, key])
    if entity_id := entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id):
        entity_registry.async_remove(entity_id)


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
            if not isinstance(data, dict) or part not in data:
                _LOGGER.debug(
                    "Key not found in data: %s", self.entity_description.key
                )
                return None
            data = data[part]
        value = data

        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if self.entity_description.key in UTC_TIME_KEYS:
                return remeha_utc_time(value)
            return remeha_time(value)

        if value is None:
            return None

        if value_function := VALUE_FUNCTIONS.get(self.entity_description.key):
            value = value_function(value)

        options = self.entity_description.options
        if options is not None and value not in options:
            # An enum sensor fails on a value outside its options, so show it as unknown
            _LOGGER.debug(
                "Unexpected value for %s: %s", self.entity_description.key, value
            )
            return None

        return value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return self.coordinator.get_device_info(self.item_id)


class RemehaHomeClockProgramSensor(RemehaHomeSensor):
    """The active clock program of a zone, with its week schedule as an attribute.

    The schedule has the same shape for heating and hot water: per day, Monday
    first, a list of switching points with time, mode and setpoint.
    """

    # The schedule rarely changes and is large, so keep it out of the database
    _unrecorded_attributes = frozenset({"schedule"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the number and the week schedule of the active clock program."""
        zone = self._data or {}
        program = zone.get(self.entity_description.key)
        time_program = self.coordinator.get_time_program(self.item_id, program)
        if self.entity_description.key == "activeDwhTimeProgramNumber":
            schedule = hot_water_schedule(time_program, zone)
        else:
            schedule = heating_schedule(
                time_program, self.coordinator.get_activities(self.item_id)
            )
        return {"program": program, "schedule": schedule}


CLOCK_PROGRAM_KEYS = {
    "activeDwhTimeProgramNumber",
    "activeHeatingClimateTimeProgramNumber",
}


def _sensor_class(
    entity_description: SensorEntityDescription,
) -> type[RemehaHomeSensor]:
    """Return the sensor class for an entity description."""
    if entity_description.key in CLOCK_PROGRAM_KEYS:
        return RemehaHomeClockProgramSensor
    return RemehaHomeSensor
