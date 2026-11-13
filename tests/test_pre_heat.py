"""Test the switch that turns pre-heat of a climate zone on or off."""

from __future__ import annotations

import copy

import pytest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import APPLIANCE_ID, CLIMATE_ZONE_ID, entity_id, setup_integration

KEY = "preHeat.enabled"
OTHER_ZONE_ID = "00000000-0000-0000-0000-00000000c002"


def switch(hass: HomeAssistant) -> str | None:
    """Return the entity id of the pre-heat switch."""
    return entity_id(hass, "switch", CLIMATE_ZONE_ID, KEY)


async def turn(hass: HomeAssistant, service: str) -> None:
    """Turn the pre-heat switch on or off."""
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: switch(hass)}, blocking=True
    )


async def test_switch(hass: HomeAssistant, config_entry, mock_api) -> None:
    """The switch shows whether pre-heat is on, as a setting of the zone."""
    await setup_integration(hass, config_entry, mock_api)

    state = hass.states.get(switch(hass))
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == "Woonkamer Pre-heat"
    entry = er.async_get(hass).async_get(switch(hass))
    assert entry.entity_category is EntityCategory.CONFIG
    sensor = entity_id(hass, "binary_sensor", CLIMATE_ZONE_ID, "preHeat.active")
    assert hass.states.get(sensor).attributes["friendly_name"] == (
        "Woonkamer Pre-heat active"
    )


@pytest.mark.parametrize(
    ("service", "enabled", "expected"),
    [(SERVICE_TURN_ON, True, STATE_ON), (SERVICE_TURN_OFF, False, STATE_OFF)],
)
async def test_turn_on_and_off(
    hass: HomeAssistant, config_entry, mock_api, climate_zone, service, enabled, expected
) -> None:
    """Turning the switch sends pre-heat for the zone."""
    climate_zone["preHeat"] = {"enabled": not enabled, "active": False}
    await setup_integration(hass, config_entry, mock_api)
    # Like the appliance, the next read reports the new setting
    climate_zone["preHeat"] = {"enabled": enabled, "active": False}

    await turn(hass, service)

    mock_api.async_set_pre_heat.assert_awaited_once_with(
        APPLIANCE_ID, {CLIMATE_ZONE_ID: enabled}
    )
    assert hass.states.get(switch(hass)).state == expected


async def test_other_zones_keep_their_setting(
    hass: HomeAssistant, config_entry, mock_api, appliance, climate_zone
) -> None:
    """The request lists every zone of the appliance, the others unchanged."""
    other = copy.deepcopy(climate_zone)
    other.update(climateZoneId=OTHER_ZONE_ID, name="Zolder")
    other["preHeat"] = {"enabled": True, "active": False}
    appliance["climateZones"].append(other)
    await setup_integration(hass, config_entry, mock_api)

    await turn(hass, SERVICE_TURN_ON)

    mock_api.async_set_pre_heat.assert_awaited_once_with(
        APPLIANCE_ID, {CLIMATE_ZONE_ID: True, OTHER_ZONE_ID: True}
    )


async def test_refused_change_is_reverted(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """When the API refuses, the switch shows the old setting again."""
    await setup_integration(hass, config_entry, mock_api)
    mock_api.async_set_pre_heat.side_effect = RuntimeError("refused")

    with pytest.raises(RuntimeError):
        await turn(hass, SERVICE_TURN_ON)

    assert hass.states.get(switch(hass)).state == STATE_OFF


async def test_no_switch_without_capability(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """An appliance without pre-heat gets no switch."""
    appliance["capabilityPreHeat"] = False
    await setup_integration(hass, config_entry, mock_api)

    assert switch(hass) is None


async def test_no_switch_without_pre_heat_data(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """A zone that doesn't report pre-heat gets no switch."""
    del climate_zone["preHeat"]
    await setup_integration(hass, config_entry, mock_api)

    assert switch(hass) is None
