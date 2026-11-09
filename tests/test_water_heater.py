"""Test changing the hot water temperature."""

from __future__ import annotations

from unittest.mock import MagicMock

from aiohttp import ClientResponseError
from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
import pytest

from .conftest import setup_integration

WATER_HEATER = "water_heater.dhw"


async def test_failed_temperature_change_keeps_the_old_temperature(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """When the API refuses the new temperature, the old one is shown again."""
    error = ClientResponseError(MagicMock(), (), status=500)
    mock_api.async_set_dhw_comfort_setpoint.side_effect = error
    mock_api.async_set_dhw_reduced_setpoint.side_effect = error
    await setup_integration(hass, config_entry, mock_api)
    old_temperature = hass.states.get(WATER_HEATER).attributes[ATTR_TEMPERATURE]

    with pytest.raises(ClientResponseError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: WATER_HEATER, ATTR_TEMPERATURE: old_temperature - 5},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get(WATER_HEATER).attributes[ATTR_TEMPERATURE] == old_temperature
    # Also in the data of the coordinator, which the next state update shows
    entity = hass.data[WATER_HEATER_DOMAIN].get_entity(WATER_HEATER)
    assert entity.target_temperature == old_temperature
