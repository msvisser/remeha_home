"""Test the temperature members of the climate and water heater entities."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.core import HomeAssistant
import pytest

from custom_components.remeha_home.climate import RemehaHomeClimateEntity
from custom_components.remeha_home.water_heater import RemehaHomeWaterHeater

from .conftest import setup_integration

NATIVE = {
    "_attr_native_temperature_unit",
    "native_current_temperature",
    "native_target_temperature",
}
DEPRECATED = {"_attr_temperature_unit", "current_temperature", "target_temperature"}


@pytest.mark.parametrize(
    ("entity_class", "base"),
    [
        (RemehaHomeClimateEntity, ClimateEntity),
        (RemehaHomeWaterHeater, WaterHeaterEntity),
    ],
)
def test_temperature_members(entity_class: type, base: type) -> None:
    """The entities provide the temperature members of this Home Assistant version.

    Home Assistant 2026.11 added the native members and logs a warning for the old
    names until they stop working in 2027.11. Earlier versions only have the old names.
    """
    members = set(vars(entity_class))
    if hasattr(base, "native_temperature_unit"):
        assert members >= NATIVE
        assert not DEPRECATED & members
    else:
        assert members >= DEPRECATED
        assert not NATIVE & members


async def test_temperatures(
    hass: HomeAssistant, config_entry, mock_api, climate_zone, hot_water_zone
) -> None:
    """The climate and water heater show the temperatures of the dashboard."""
    climate_zone["roomTemperature"] = 19.5
    climate_zone["setPoint"] = 20.5
    hot_water_zone["dhwTemperature"] = 48.0
    hot_water_zone["dhwZoneMode"] = "ContinuousComfort"
    hot_water_zone["comfortSetPoint"] = 55.0
    await setup_integration(hass, config_entry, mock_api)

    climate = hass.states.get("climate.woonkamer")
    assert climate.attributes["current_temperature"] == 19.5
    assert climate.attributes["temperature"] == 20.5
    water_heater = hass.states.get("water_heater.dhw")
    assert water_heater.attributes["current_temperature"] == 48.0
    assert water_heater.attributes["temperature"] == 55.0
