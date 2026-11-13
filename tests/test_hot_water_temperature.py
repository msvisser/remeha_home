"""Test the water temperature sensor of a hot water zone."""

from __future__ import annotations

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.remeha_home.const import DOMAIN

from .conftest import HOT_WATER_ZONE_ID, entity_id, setup_integration

KEY = "dhwTemperature"


def add_old_sensor(hass: HomeAssistant, config_entry) -> str:
    """Add the water temperature sensor to the registry, as an earlier version did."""
    return (
        er.async_get(hass)
        .async_get_or_create(
            "sensor",
            DOMAIN,
            f"{DOMAIN}_{HOT_WATER_ZONE_ID}_{KEY}",
            config_entry=config_entry,
        )
        .entity_id
    )


async def test_combi_without_temperature(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """A combi boiler without a temperature gets no sensor, the old one is removed."""
    config_entry.add_to_hass(hass)
    add_old_sensor(hass, config_entry)
    await setup_integration(hass, config_entry, mock_api)

    assert entity_id(hass, "sensor", HOT_WATER_ZONE_ID, KEY) is None
    # The other hot water sensors are still there
    assert entity_id(hass, "sensor", HOT_WATER_ZONE_ID, "dhwCurrentActivity")
    assert hass.states.get("water_heater.dhw").attributes["current_temperature"] is None


async def test_combi_with_temperature(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone
) -> None:
    """A combi boiler that reports a temperature keeps the sensor."""
    hot_water_zone["dhwTemperature"] = 48.5
    await setup_integration(hass, config_entry, mock_api)

    state = hass.states.get(entity_id(hass, "sensor", HOT_WATER_ZONE_ID, KEY))
    assert state.state == "48.5"


async def test_tank_with_temperature(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone
) -> None:
    """A tank shows its temperature."""
    hot_water_zone["dhwType"] = "Tank"
    hot_water_zone["dhwTemperature"] = 52.0
    await setup_integration(hass, config_entry, mock_api)

    state = hass.states.get(entity_id(hass, "sensor", HOT_WATER_ZONE_ID, KEY))
    assert state.state == "52.0"


async def test_tank_without_temperature(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone
) -> None:
    """A tank keeps its sensor and entity when the temperature is missing for a while."""
    hot_water_zone["dhwType"] = "Tank"
    config_entry.add_to_hass(hass)
    old_entity_id = add_old_sensor(hass, config_entry)
    await setup_integration(hass, config_entry, mock_api)

    assert entity_id(hass, "sensor", HOT_WATER_ZONE_ID, KEY) == old_entity_id
    assert hass.states.get(old_entity_id).state == STATE_UNKNOWN
