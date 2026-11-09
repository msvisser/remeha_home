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
    UnitOfVolume,
)

DOMAIN = "remeha_home"

# Personal data in the API responses, redacted in the diagnostics and the debug log.
# The ids (applianceId, climateZoneId, ...) are kept: they are random, and needed
# to match the data to the entities.
TO_REDACT = {
    # The config entry is titled with the email address used to log in
    "title",
    "token",
    # Names typed in the Remeha Home app: home, zones and activities
    "houseName",
    "name",
    "controlledZoneName",
    # Identify the hardware: serial number of a gateway, device index of a producer
    "serialNumber",
    "deviceIndex",
}

# The clock programs, the presets of the climate entity
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

# The presets shown in heat (or heat/cool) mode and in off mode
PRESET_MANUAL = "manual"
PRESET_ANTI_FROST = "anti_frost"

APPLIANCE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="waterPressure",
        name="Water Pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="activeThermalMode",
        name="Thermal Mode",
    ),
    SensorEntityDescription(
        # What the appliance is set to do, the thermal mode is what it is doing now
        key="operatingMode",
        name="Operating Mode",
    ),
    SensorEntityDescription(
        key="errorStatus",
        name="Error Status",
        icon="mdi:alert-circle-outline",
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

ELECTRIC_PRODUCER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="energyConsumptionCH",
        name="Heating Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyConsumptionDHW",
        name="Hot Water Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyConsumptionCooling",
        name="Cooling Energy Consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionCH",
        name="Heating Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionDHW",
        name="Hot Water Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyProductionCooling",
        name="Cooling Energy Delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        # Running seasonal value (SCOP) reported by Remeha, not the efficiency of the day
        key="seasonalEfficiency",
        name="Seasonal Efficiency",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

GAS_PRODUCER_SENSOR_TYPES = [
    SensorEntityDescription(
        key="energyConsumptionCH",
        name="Heating Energy Consumed",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyConsumptionDHW",
        name="Hot Water Energy Consumed",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )
]

CLIMATE_ZONE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="roomTemperature",
        name="Room Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="activeComfortDemand",
        name="Status",
    ),
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
    SensorEntityDescription(
        key="temporaryOverride.endTime",
        name="Override End",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

HEATING_CURVE_SENSOR_TYPES = [
    SensorEntityDescription(
        key="heatingCurve.maxFlowTemperature",
        translation_key="heating_curve_max_flow_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
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
    SensorEntityDescription(
        key="dhwCurrentActivity",
        name="Mode",
    ),
    SensorEntityDescription(
        key="nextSwitchTime",
        name="Next Setpoint Time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        # The next activity of the clock program (Comfort or Eco), also reported when
        # the zone doesn't follow the clock program
        key="nextSwitchActivity",
        name="Next Mode",
    ),
    SensorEntityDescription(
        # The active clock program, with the names of the presets of the climate entity
        key="activeDwhTimeProgramNumber",
        translation_key="clock_program",
        device_class=SensorDeviceClass.ENUM,
        options=list(PRESET_INDEX_TO_PRESET_MODE.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
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
        # Remeha reports whether the pressure is OK, a problem sensor is on when it isn't
        lambda value: not value,
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
        lambda value: value
        in ["ProducingHeat", "RequestingHeat", "ProducingCold", "RequestingCold"],
    ),
    (
        BinarySensorEntityDescription(
            key="preHeat.active",
            name="Pre-heat",
            icon="mdi:clock-start",
        ),
        lambda value: bool(value),
    ),
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

# Only for appliances that support hot water optimization (capabilityDhwOptimization):
# the zone also reports the setting when the appliance doesn't support it
HOT_WATER_ZONE_OPTIMIZATION_BINARY_SENSOR_TYPES = [
    (
        BinarySensorEntityDescription(
            key="optimizationEnabled",
            name="Optimization",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        lambda value: bool(value),
    ),
]
