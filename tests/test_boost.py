"""Test the remaining boost time of the water heater."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

# Measured on a live system: a 30 minute boost started at 14:41:59 CEST
STARTED = "2026-10-22T12:41:59+00:00"
END_TIME = "2026-10-22T13:11:59.2692621Z"


@pytest.fixture(autouse=True)
async def amsterdam(hass: HomeAssistant) -> None:
    """Use the time zone of the measurement."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")


async def test_remaining_boost_time(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone, freezer
) -> None:
    """The boost end time is in UTC, unlike the other times of the API."""
    freezer.move_to(STARTED)
    hot_water_zone["dhwZoneMode"] = "Boost"
    hot_water_zone["boostModeEndTime"] = END_TIME
    await setup_integration(hass, config_entry, mock_api)

    water_heater = hass.states.get("water_heater.dhw")
    assert water_heater.state == "high_demand"
    assert water_heater.attributes["remaining_boost_time"] == "30 minutes"
    assert hass.states.get("switch.dhw_boost").state == "on"


async def test_no_boost(hass: HomeAssistant, config_entry, mock_api) -> None:
    """Without a boost there is no remaining boost time."""
    await setup_integration(hass, config_entry, mock_api)

    water_heater = hass.states.get("water_heater.dhw")
    assert "remaining_boost_time" not in water_heater.attributes
    assert hass.states.get("switch.dhw_boost").state == "off"
