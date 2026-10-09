"""Constants for the Remeha Home integration."""

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfPressure,
)

DOMAIN = "remeha_home"

APPLIANCE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="waterPressure",
        name="Water Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="errorStatus",
        name="Error Status",
        icon="mdi:alert-circle-outline",
    ),
    SensorEntityDescription(
        key="operatingMode",
        name="Operating Mode",
        icon="mdi:cog-outline",
    ),
    SensorEntityDescription(
        key="activeThermalMode",
        name="Thermal Mode",
        icon="mdi:heat-wave",
    ),
    SensorEntityDescription(
        key="outdoorTemperatureInformation.applianceOutdoorTemperature",
        name="Outdoor Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="outdoorTemperatureInformation.cloudOutdoorTemperature",
        name="Cloud Outdoor Temperature",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="consumptionData.heatingEnergyConsumed",
        name="Heating Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.hotWaterEnergyConsumed",
        name="Hot Water Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.coolingEnergyConsumed",
        name="Cooling Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.heatingEnergyDelivered",
        name="Heating Energy Delivered",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.hotWaterEnergyDelivered",
        name="Hot Water Energy Delivered",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.coolingEnergyDelivered",
        name="Cooling Energy Delivered",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]

CLIMATE_ZONE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="nextSetpoint",
        name="Next Setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="nextSwitchTime",
        name="Next Setpoint Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="currentScheduleSetPoint",
        name="Current Schedule Setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
]

HOT_WATER_ZONE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="dhwTemperature",
        name="Water Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dhwStatus",
        name="Status",
        entity_registry_enabled_default=False,
    ),
]

APPLIANCE_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="applianceOnline",
            name="Online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        lambda value: bool(value),
    ),
    (
        BinarySensorEntityDescription(
            key="waterPressureOK",
            name="Water Pressure",
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
        # The API reports whether the pressure is OK; a problem sensor is on when it is not
        lambda value: not value,
    ),
    (
        BinarySensorEntityDescription(
            key="holidaySchedule.active",
            name="Holiday Mode",
            icon="mdi:bag-suitcase",
        ),
        lambda value: bool(value),
    ),
]

CLIMATE_ZONE_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="activeComfortDemand",
            name="Status",
            entity_registry_enabled_default=False,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        lambda value: value in ["ProducingHeat", "RequestingHeat"],
    )
]

HOT_WATER_ZONE_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="dhwStatus",
            name="Status",
            entity_registry_enabled_default=False,
            device_class=BinarySensorDeviceClass.HEAT,
        ),
        lambda value: value == "ProducingHeat",
    ),
]
