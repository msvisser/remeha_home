"""Test that heat/cool is only offered for climate zones that can cool."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import CLIMATE_ZONE_ID, setup_integration

CLIMATE = "climate.woonkamer"


def assert_manual_mode(hass: HomeAssistant, manual_mode: HVACMode) -> None:
    """Assert that the zone shows and offers this mode for the Remeha manual mode."""
    climate = hass.states.get(CLIMATE)
    assert climate.state == manual_mode
    assert climate.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        manual_mode,
    ]


async def test_heat_pump_that_cant_cool(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """A heat pump that reports it can't cool shows heat, not heat/cool."""
    assert appliance["applianceType"] == "HeatPump"
    assert appliance["capabilityCooling"] is False
    assert climate_zone["capabilityCooling"] is False
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT)


async def test_zone_that_can_cool(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """A zone that can cool shows heat/cool."""
    appliance["capabilityCooling"] = True
    climate_zone["capabilityCooling"] = True
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT_COOL)


async def test_zone_capability_comes_first(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """A zone that can't cool shows heat, also when its appliance can cool."""
    appliance["capabilityCooling"] = True
    climate_zone["capabilityCooling"] = False
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT)


async def test_appliance_capability_without_zone_capability(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """Without the capability of the zone, the appliance's capability counts."""
    appliance["capabilityCooling"] = True
    del climate_zone["capabilityCooling"]
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT_COOL)


@pytest.mark.parametrize(
    ("appliance_type", "manual_mode"),
    [("HeatPump", HVACMode.HEAT_COOL), ("Boiler", HVACMode.HEAT)],
)
async def test_without_capability(
    hass: HomeAssistant,
    config_entry,
    mock_api,
    appliance,
    climate_zone,
    appliance_type,
    manual_mode,
) -> None:
    """Without any capabilityCooling, a heat pump is assumed to cool, as before."""
    appliance["applianceType"] = appliance_type
    del appliance["capabilityCooling"]
    del climate_zone["capabilityCooling"]
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, manual_mode)


@pytest.mark.parametrize(
    ("can_cool", "manual_mode"),
    [(False, HVACMode.HEAT), (True, HVACMode.HEAT_COOL)],
)
async def test_set_manual_mode(
    hass: HomeAssistant,
    config_entry,
    mock_api,
    appliance,
    climate_zone,
    can_cool,
    manual_mode,
) -> None:
    """The mode the zone offers for the manual mode sets the manual mode."""
    appliance["capabilityCooling"] = can_cool
    climate_zone["capabilityCooling"] = can_cool
    climate_zone["zoneMode"] = "Scheduling"
    await setup_integration(hass, config_entry, mock_api)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_HVAC_MODE: manual_mode},
        blocking=True,
    )

    mock_api.async_set_manual.assert_awaited_once_with(
        CLIMATE_ZONE_ID, climate_zone["setPoint"]
    )
