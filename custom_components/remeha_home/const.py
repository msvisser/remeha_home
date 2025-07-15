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
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfPressure

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
    SensorEntityDescription(
        key="consumptionData.energyConsumptionCHElectric",
        name="Electric Heating Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionDHWElectric",
        name="Electric Hot Water Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionCoolingElectric",
        name="Electric Cooling Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionTotalElectric",
        name="Total Electric Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionCHElectric",
        name="Electric Heating Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionDHWElectric",
        name="Electric Hot Water Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionCoolingElectric",
        name="Electric Cooling Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionTotalElectric",
        name="Total Electric Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionCHNaturalGas",
        name="Natural Gas Heating Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionDHWNaturalGas",
        name="Natural Gas Hot Water Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionCoolingNaturalGas",
        name="Natural Gas Cooling Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyConsumptionTotalNaturalGas",
        name="Total Natural Gas Energy Consumed",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionCHNaturalGas",
        name="Natural Gas Heating Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionDHWNaturalGas",
        name="Natural Gas Hot Water Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionCoolingNaturalGas",
        name="Natural Gas Cooling Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.energyProductionTotalNaturalGas",
        name="Total Natural Gas Cooling Energy Produced",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="consumptionData.seasonalEfficiencyElectric",
        name="Electric Seasonal Efficiency",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
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
