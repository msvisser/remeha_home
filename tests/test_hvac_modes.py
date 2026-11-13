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

from custom_components.remeha_home.const import DOMAIN

from .conftest import CLIMATE_ZONE_ID, load_fixture, refresh, setup_integration

CLIMATE = "climate.woonkamer"


def heating_activities() -> list[dict]:
    """Return the activities of a zone that only heats, such as one on radiators."""
    return [
        activity
        for activity in load_fixture("activities.json")
        if activity["type"] == "Heating"
    ]


def assert_manual_mode(hass: HomeAssistant, manual_mode: HVACMode) -> None:
    """Assert that the zone shows and offers this mode for the Remeha manual mode."""
    climate = hass.states.get(CLIMATE)
    assert climate.state == manual_mode
    assert climate.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        manual_mode,
    ]


async def test_cooling_activities(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """A zone with Cooling activities shows heat/cool, also with capabilityCooling false."""
    assert appliance["capabilityCooling"] is False
    assert climate_zone["capabilityCooling"] is False
    assert any(
        activity["type"] == "Cooling" for activity in load_fixture("activities.json")
    )
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT_COOL)


async def test_heating_activities_only(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """A heat pump zone that can't cool and has only Heating activities shows heat."""
    assert appliance["applianceType"] == "HeatPump"
    mock_api.async_get_activities.return_value = heating_activities()
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT)


async def test_zone_that_can_cool(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """A zone that reports it can cool shows heat/cool, whatever its activities."""
    climate_zone["capabilityCooling"] = True
    mock_api.async_get_activities.return_value = heating_activities()
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT_COOL)


async def test_zone_capability_comes_first(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """A zone that can't cool shows heat, also when its appliance can cool."""
    appliance["capabilityCooling"] = True
    climate_zone["capabilityCooling"] = False
    mock_api.async_get_activities.return_value = heating_activities()
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT)


async def test_appliance_capability_without_zone_capability(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """Without the capability of the zone, the appliance's capability counts."""
    appliance["capabilityCooling"] = True
    del climate_zone["capabilityCooling"]
    mock_api.async_get_activities.return_value = heating_activities()
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, HVACMode.HEAT_COOL)


@pytest.mark.parametrize(
    ("appliance_type", "manual_mode"),
    [("HeatPump", HVACMode.HEAT_COOL), ("Boiler", HVACMode.HEAT)],
)
async def test_activities_never_fetched(
    hass: HomeAssistant,
    config_entry,
    mock_api,
    appliance,
    appliance_type,
    manual_mode,
) -> None:
    """Before the activities have been fetched, a heat pump is assumed to cool."""
    appliance["applianceType"] = appliance_type
    mock_api.async_get_activities.side_effect = TimeoutError
    await setup_integration(hass, config_entry, mock_api)

    assert_manual_mode(hass, manual_mode)


async def test_activities_missing_keeps_last_result(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """While the activities are missing for a moment, the last result is kept."""
    mock_api.async_get_activities.return_value = heating_activities()
    await setup_integration(hass, config_entry, mock_api)
    assert_manual_mode(hass, HVACMode.HEAT)

    # As after an activity is changed: the activities are dropped and fetched again,
    # which fails this time
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    coordinator.activities_data.pop(CLIMATE_ZONE_ID)
    mock_api.async_get_activities.side_effect = TimeoutError
    await refresh(hass, config_entry)

    assert coordinator.get_activities(CLIMATE_ZONE_ID) is None
    assert_manual_mode(hass, HVACMode.HEAT)


@pytest.mark.parametrize(
    ("can_cool", "manual_mode"),
    [(False, HVACMode.HEAT), (True, HVACMode.HEAT_COOL)],
)
async def test_set_manual_mode(
    hass: HomeAssistant,
    config_entry,
    mock_api,
    climate_zone,
    can_cool,
    manual_mode,
) -> None:
    """The mode the zone offers for the manual mode sets the manual mode."""
    climate_zone["capabilityCooling"] = can_cool
    climate_zone["zoneMode"] = "Scheduling"
    mock_api.async_get_activities.return_value = heating_activities()
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
