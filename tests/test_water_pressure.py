"""Test the water pressure sensors of an appliance that doesn't report a pressure."""

from __future__ import annotations

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import APPLIANCE_ID, entity_id, refresh, setup_integration

PRESSURE = "waterPressure"
PROBLEM = "waterPressureOK"


def no_pressure(appliance: dict) -> None:
    """Report no pressure, like a Brötje BOK19 with only an analog gauge."""
    appliance["waterPressure"] = None
    appliance["waterPressureOK"] = False


async def test_reported_pressure(hass: HomeAssistant, config_entry, mock_api) -> None:
    """An appliance that reports its pressure gets both sensors."""
    await setup_integration(hass, config_entry, mock_api)

    assert hass.states.get(entity_id(hass, "sensor", APPLIANCE_ID, PRESSURE)).state == "1.7"
    problem = entity_id(hass, "binary_sensor", APPLIANCE_ID, PROBLEM)
    assert hass.states.get(problem).state == STATE_OFF


async def test_no_pressure_no_sensors(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """Without a pressure, no sensors are created, so no false problem shows."""
    no_pressure(appliance)
    await setup_integration(hass, config_entry, mock_api)

    assert entity_id(hass, "sensor", APPLIANCE_ID, PRESSURE) is None
    assert entity_id(hass, "binary_sensor", APPLIANCE_ID, PROBLEM) is None


async def test_sensors_created_before_are_removed(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """Sensors created by an earlier version are removed at the next setup."""
    await setup_integration(hass, config_entry, mock_api)
    assert entity_id(hass, "binary_sensor", APPLIANCE_ID, PROBLEM) is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    no_pressure(appliance)
    await setup_integration(hass, config_entry, mock_api)

    assert entity_id(hass, "sensor", APPLIANCE_ID, PRESSURE) is None
    assert entity_id(hass, "binary_sensor", APPLIANCE_ID, PROBLEM) is None


async def test_pressure_missing_later(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """When the pressure goes missing after setup, the problem sensor is unknown."""
    await setup_integration(hass, config_entry, mock_api)
    no_pressure(appliance)

    await refresh(hass, config_entry)

    problem = entity_id(hass, "binary_sensor", APPLIANCE_ID, PROBLEM)
    assert hass.states.get(problem).state == STATE_UNKNOWN


async def test_real_problem_still_shows(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """With a pressure, waterPressureOK false is still a problem."""
    appliance["waterPressureOK"] = False
    await setup_integration(hass, config_entry, mock_api)

    problem = entity_id(hass, "binary_sensor", APPLIANCE_ID, PROBLEM)
    assert hass.states.get(problem).state == STATE_ON
