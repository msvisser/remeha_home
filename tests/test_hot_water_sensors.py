"""Test the next mode and clock program sensors of a hot water zone."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from homeassistant.const import STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.remeha_home.const import DOMAIN

from .conftest import (
    CLIMATE_ZONE_ID,
    HOT_WATER_ZONE_ID,
    entity_id,
    refresh,
    setup_integration,
)

NEXT_MODE = "nextSwitchActivity"
CLOCK_PROGRAM = "activeDwhTimeProgramNumber"

TRANSLATIONS = (
    Path(__file__).parent.parent / "custom_components" / "remeha_home" / "translations"
)


def sensor(hass: HomeAssistant, key: str):
    """Return the state of a hot water zone sensor."""
    return hass.states.get(entity_id(hass, "sensor", HOT_WATER_ZONE_ID, key))


async def test_next_mode(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone
) -> None:
    """The Next Mode sensor shows the next activity of the clock program."""
    await setup_integration(hass, config_entry, mock_api)
    state = sensor(hass, NEXT_MODE)
    assert state.state == "Comfort"
    assert state.attributes["friendly_name"] == "DHW Next Mode"

    # The API calls Eco "Reduced", the Mode sensor and the Remeha Home app call it Eco
    hot_water_zone["nextSwitchActivity"] = "Reduced"
    await refresh(hass, config_entry)
    assert sensor(hass, NEXT_MODE).state == "Eco"


async def test_next_mode_unknown(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone, caplog
) -> None:
    """A next mode that becomes null or missing is unknown, not an error."""
    await setup_integration(hass, config_entry, mock_api)

    hot_water_zone["nextSwitchActivity"] = None
    await refresh(hass, config_entry)
    assert sensor(hass, NEXT_MODE).state == STATE_UNKNOWN

    del hot_water_zone["nextSwitchActivity"]
    await refresh(hass, config_entry)
    assert sensor(hass, NEXT_MODE).state == STATE_UNKNOWN
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_clock_program(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone
) -> None:
    """The Clock program sensor shows the active program, like the climate presets."""
    await setup_integration(hass, config_entry, mock_api)
    state = sensor(hass, CLOCK_PROGRAM)
    assert state.state == "clock_program_1"
    assert state.attributes["friendly_name"] == "DHW Clock program"
    assert state.attributes["options"] == [
        "clock_program_1",
        "clock_program_2",
        "clock_program_3",
    ]
    climate = er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, f"{DOMAIN}_{CLIMATE_ZONE_ID}"
    )
    # The clock programs have the same names as the clock program presets
    assert state.attributes["options"] == [
        preset
        for preset in hass.states.get(climate).attributes["preset_modes"]
        if preset.startswith("clock_program_")
    ]
    entry = er.async_get(hass).async_get(
        entity_id(hass, "sensor", HOT_WATER_ZONE_ID, CLOCK_PROGRAM)
    )
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    hot_water_zone["activeDwhTimeProgramNumber"] = 2
    await refresh(hass, config_entry)
    assert sensor(hass, CLOCK_PROGRAM).state == "clock_program_2"


@pytest.mark.parametrize("value", [None, 4, "missing"])
async def test_clock_program_unknown(
    hass: HomeAssistant, config_entry, mock_api, hot_water_zone, caplog, value
) -> None:
    """A null, missing or unexpected clock program is unknown, not an error."""
    await setup_integration(hass, config_entry, mock_api)

    if value == "missing":
        del hot_water_zone["activeDwhTimeProgramNumber"]
    else:
        hot_water_zone["activeDwhTimeProgramNumber"] = value
    await refresh(hass, config_entry)
    assert sensor(hass, CLOCK_PROGRAM).state == STATE_UNKNOWN
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.parametrize("language", ["en", "nl", "fr", "pl"])
def test_clock_program_names(language: str) -> None:
    """The clock programs have the names of the climate presets, in every language.

    The sensor itself is not named after the Schedule mode of the water heater, which
    doesn't always follow the clock program.
    """
    entity = json.loads(
        (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
    )["entity"]
    presets = entity["climate"]["remeha_home"]["state_attributes"]["preset_mode"][
        "state"
    ]
    clock_program = entity["sensor"]["clock_program"]
    assert clock_program["state"] == {
        key: name for key, name in presets.items() if key.startswith("clock_program_")
    }
    assert (
        clock_program["name"]
        != entity["water_heater"]["remeha_home_dhw"]["state"]["heat_pump"]
    )
