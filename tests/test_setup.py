"""Test that the integration sets up with the fixtures."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import (
    APPLIANCE_ID,
    CLIMATE_ZONE_ID,
    HOT_WATER_ZONE_ID,
    entity_id,
    setup_integration,
)


async def test_setup(hass: HomeAssistant, config_entry, mock_api, caplog) -> None:
    """Set up without errors and create the main entities."""
    await setup_integration(hass, config_entry, mock_api)

    assert config_entry.state is ConfigEntryState.LOADED
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    for platform, item_id, key in (
        ("sensor", APPLIANCE_ID, "waterPressure"),
        ("sensor", CLIMATE_ZONE_ID, "roomTemperature"),
        ("sensor", HOT_WATER_ZONE_ID, "dhwCurrentActivity"),
        ("binary_sensor", APPLIANCE_ID, "holidaySchedule"),
        ("switch", HOT_WATER_ZONE_ID, "boost"),
        ("number", HOT_WATER_ZONE_ID, "comfortSetPoint"),
    ):
        entity = entity_id(hass, platform, item_id, key)
        assert entity is not None, (platform, key)
        assert hass.states.get(entity) is not None, entity

    climate = hass.states.get("climate.woonkamer")
    assert climate is not None
    assert climate.state == "heat_cool"
    assert hass.states.get("water_heater.dhw").state == "heat_pump"
