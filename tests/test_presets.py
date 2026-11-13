"""Test the presets of the climate entity: the clock programs, manual and off."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import CLIMATE_ZONE_ID, load_fixture, setup_integration

CLIMATE = "climate.woonkamer"


def act_like_the_appliance(mock_api, climate_zone: dict) -> None:
    """Let the mocked API change the zone, like the appliance does."""

    def set_mode(mode: str):
        return lambda *args: climate_zone.update(zoneMode=mode)

    def activate(_zone_id, program: int) -> None:
        climate_zone["activeHeatingClimateTimeProgramNumber"] = program

    mock_api.async_set_manual.side_effect = set_mode("Manual")
    mock_api.async_set_off.side_effect = set_mode("FrostProtection")
    mock_api.async_set_schedule.side_effect = set_mode("Scheduling")
    mock_api.async_activate_heating_time_program.side_effect = activate


async def set_preset(hass: HomeAssistant, preset_mode: str) -> None:
    """Select a preset on the climate zone."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: CLIMATE, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )


async def test_preset_modes(hass: HomeAssistant, config_entry, mock_api) -> None:
    """Manual and frost protection can be selected, after the clock programs."""
    await setup_integration(hass, config_entry, mock_api)

    assert hass.states.get(CLIMATE).attributes[ATTR_PRESET_MODES] == [
        "clock_program_1",
        "clock_program_2",
        "clock_program_3",
        "manual",
        "anti_frost",
    ]


@pytest.mark.parametrize(
    ("cooling_activities", "state"), [(True, "heat_cool"), (False, "heat")]
)
async def test_manual_preset(
    hass: HomeAssistant,
    config_entry,
    mock_api,
    climate_zone,
    cooling_activities,
    state,
) -> None:
    """Manual sets the manual mode with the current setpoint, in heat or heat/cool."""
    climate_zone["zoneMode"] = "Scheduling"
    if not cooling_activities:
        mock_api.async_get_activities.return_value = [
            activity
            for activity in load_fixture("activities.json")
            if activity["type"] == "Heating"
        ]
    await setup_integration(hass, config_entry, mock_api)
    act_like_the_appliance(mock_api, climate_zone)

    await set_preset(hass, "manual")

    mock_api.async_set_manual.assert_awaited_once_with(
        CLIMATE_ZONE_ID, climate_zone["setPoint"]
    )
    assert hass.states.get(CLIMATE).state == state
    assert hass.states.get(CLIMATE).attributes[ATTR_PRESET_MODE] == "manual"


async def test_anti_frost_preset(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """Frost protection turns the zone off."""
    climate_zone["zoneMode"] = "Scheduling"
    await setup_integration(hass, config_entry, mock_api)
    act_like_the_appliance(mock_api, climate_zone)

    await set_preset(hass, "anti_frost")

    mock_api.async_set_off.assert_awaited_once_with(CLIMATE_ZONE_ID)
    assert hass.states.get(CLIMATE).state == "off"
    assert hass.states.get(CLIMATE).attributes[ATTR_PRESET_MODE] == "anti_frost"


async def test_failed_preset_is_reverted(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """When the API refuses, the zone shows its old mode again."""
    climate_zone["zoneMode"] = "Scheduling"
    await setup_integration(hass, config_entry, mock_api)
    mock_api.async_set_off.side_effect = RuntimeError("refused")

    with pytest.raises(RuntimeError):
        await set_preset(hass, "anti_frost")

    assert hass.states.get(CLIMATE).state == "auto"
    assert hass.states.get(CLIMATE).attributes[ATTR_PRESET_MODE] == "clock_program_1"


async def test_clock_program_from_manual(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """A clock program still switches a manual zone back to its schedule."""
    climate_zone["zoneMode"] = "Manual"
    await setup_integration(hass, config_entry, mock_api)
    act_like_the_appliance(mock_api, climate_zone)

    await set_preset(hass, "clock_program_2")

    mock_api.async_activate_heating_time_program.assert_awaited_once_with(
        CLIMATE_ZONE_ID, 2
    )
    mock_api.async_set_schedule.assert_awaited_once_with(CLIMATE_ZONE_ID, 2)
    assert hass.states.get(CLIMATE).state == "auto"


async def test_clock_program_from_another_program(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """Switching programs also selects schedule mode for the new one.

    Activating a program alone has left a zone on the setpoint of the program it left
    (18.5 from 'Away') while its own schedule setpoint was the new program's (19.5);
    selecting schedule mode made it follow the schedule at once.
    """
    climate_zone.update(
        zoneMode="Scheduling",
        activeHeatingClimateTimeProgramNumber=3,
        setPoint=18.5,
        currentScheduleSetPoint=19.5,
    )
    await setup_integration(hass, config_entry, mock_api)
    act_like_the_appliance(mock_api, climate_zone)
    calls = []

    def activate(_zone_id, program: int) -> None:
        calls.append("activate")
        climate_zone["activeHeatingClimateTimeProgramNumber"] = program

    def set_schedule(_zone_id, _program: int) -> None:
        calls.append("schedule")
        climate_zone.update(
            zoneMode="Scheduling", setPoint=climate_zone["currentScheduleSetPoint"]
        )

    mock_api.async_activate_heating_time_program.side_effect = activate
    mock_api.async_set_schedule.side_effect = set_schedule

    await set_preset(hass, "clock_program_1")

    mock_api.async_activate_heating_time_program.assert_awaited_once_with(
        CLIMATE_ZONE_ID, 1
    )
    mock_api.async_set_schedule.assert_awaited_once_with(CLIMATE_ZONE_ID, 1)
    assert calls == ["activate", "schedule"]
    state = hass.states.get(CLIMATE)
    assert state.attributes[ATTR_PRESET_MODE] == "clock_program_1"
    assert state.attributes["temperature"] == 19.5


async def test_clock_program_keeps_a_temporary_override(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """A temporary override is left running: only the program is switched."""
    climate_zone["zoneMode"] = "TemporaryOverride"
    await setup_integration(hass, config_entry, mock_api)
    act_like_the_appliance(mock_api, climate_zone)

    await set_preset(hass, "clock_program_2")

    mock_api.async_activate_heating_time_program.assert_awaited_once_with(
        CLIMATE_ZONE_ID, 2
    )
    mock_api.async_set_schedule.assert_not_awaited()


async def test_refreshed_again_after_a_change(
    hass: HomeAssistant, config_entry, mock_api, climate_zone, freezer
) -> None:
    """The data is requested again 15 seconds after a change.

    The read right after a change can still answer with the old values, such as the
    setpoint of the clock program the zone left.
    """
    climate_zone["zoneMode"] = "Scheduling"
    await setup_integration(hass, config_entry, mock_api)
    act_like_the_appliance(mock_api, climate_zone)

    await set_preset(hass, "clock_program_2")
    await hass.async_block_till_done()
    reads = mock_api.async_get_dashboard.await_count

    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_api.async_get_dashboard.await_count == reads + 1
