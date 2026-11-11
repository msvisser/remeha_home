"""Test the Clock program sensors with the week schedule of the active program."""

from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
import pytest

from custom_components.remeha_home.schedule import (
    SCHEDULE_DAYS,
    heating_schedule,
    hot_water_schedule,
)
from custom_components.remeha_home.sensor import RemehaHomeClockProgramSensor

from .conftest import (
    CLIMATE_ZONE_ID,
    HOT_WATER_ZONE_ID,
    entity_id,
    load_fixture,
    refresh,
    setup_integration,
)

HEATING = "activeHeatingClimateTimeProgramNumber"
HOT_WATER = "activeDwhTimeProgramNumber"


def clock_program(hass: HomeAssistant, zone_id: str, key: str):
    """Return the state of a Clock program sensor."""
    return hass.states.get(entity_id(hass, "sensor", zone_id, key))


async def test_heating_schedule(hass: HomeAssistant, config_entry, mock_api) -> None:
    """The heating schedule has the activity names and temperatures, Monday first."""
    await setup_integration(hass, config_entry, mock_api)

    state = clock_program(hass, CLIMATE_ZONE_ID, HEATING)
    assert state.state == "clock_program_1"
    assert state.attributes["friendly_name"] == "Woonkamer Clock program"
    assert state.attributes["program"] == 1
    schedule = state.attributes["schedule"]
    assert list(schedule) == list(SCHEDULE_DAYS)
    assert schedule["monday"] == [
        {"time": "06:30", "mode": "Thuis", "setpoint": 20.0},
        {"time": "08:30", "mode": "Werken", "setpoint": 16.5},
        {"time": "17:00", "mode": "Thuis", "setpoint": 20.0},
        {"time": "22:30", "mode": "Slapen", "setpoint": 20.0},
    ]
    # A switching point with its own temperature uses that one
    assert schedule["saturday"][-1] == {"time": "23:00", "mode": "Slapen", "setpoint": 18.5}
    mock_api.async_get_heating_time_program.assert_awaited_once_with(CLIMATE_ZONE_ID, 1)


async def test_hot_water_schedule(hass: HomeAssistant, config_entry, mock_api) -> None:
    """The hot water schedule has Comfort and Eco; a combi boiler has no Eco setpoint."""
    await setup_integration(hass, config_entry, mock_api)

    state = clock_program(hass, HOT_WATER_ZONE_ID, HOT_WATER)
    assert state.state == "clock_program_1"
    assert state.attributes["program"] == 1
    assert state.attributes["schedule"]["sunday"] == [
        {"time": "07:00", "mode": "Comfort", "setpoint": 60.0},
        {"time": "09:30", "mode": "Eco", "setpoint": None},
        {"time": "16:00", "mode": "Comfort", "setpoint": 60.0},
        {"time": "19:30", "mode": "Eco", "setpoint": None},
    ]
    mock_api.async_get_hot_water_time_program.assert_awaited_once_with(
        HOT_WATER_ZONE_ID, 1
    )


def test_hot_water_tank_has_an_eco_setpoint() -> None:
    """A hot water tank keeps water warm in Eco, at the reduced setpoint."""
    zone = {"dhwType": "Tank", "comfortSetPoint": 55.0, "reducedSetpoint": 40.0}
    schedule = hot_water_schedule(load_fixture("time_program_hot_water.json"), zone)
    assert schedule["monday"][:2] == [
        {"time": "04:00", "mode": "Comfort", "setpoint": 55.0},
        {"time": "06:00", "mode": "Eco", "setpoint": 40.0},
    ]


async def test_other_program_is_requested(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """When another clock program becomes active, its schedule is requested at once."""
    await setup_integration(hass, config_entry, mock_api)
    climate_zone["activeHeatingClimateTimeProgramNumber"] = 2
    mock_api.async_get_heating_time_program.return_value = {
        **load_fixture("time_program_heating.json"),
        "timeProgramNumber": 2,
        "switchPoints": [{"day": 1, "time": "07:00", "activity": 3, "customValue": None}],
    }

    await refresh(hass, config_entry)

    mock_api.async_get_heating_time_program.assert_awaited_with(CLIMATE_ZONE_ID, 2)
    state = clock_program(hass, CLIMATE_ZONE_ID, HEATING)
    assert state.state == "clock_program_2"
    assert state.attributes["program"] == 2
    assert state.attributes["schedule"]["monday"] == [
        {"time": "07:00", "mode": "Afwezig", "setpoint": 19.0}
    ]


async def test_requested_every_15_minutes(
    hass: HomeAssistant, config_entry, mock_api, freezer
) -> None:
    """A change made in the Remeha Home app shows up within 15 minutes."""
    await setup_integration(hass, config_entry, mock_api)
    assert mock_api.async_get_heating_time_program.await_count == 1

    freezer.tick(timedelta(minutes=5))
    await refresh(hass, config_entry)
    assert mock_api.async_get_heating_time_program.await_count == 1

    freezer.tick(timedelta(minutes=10))
    await refresh(hass, config_entry)
    assert mock_api.async_get_heating_time_program.await_count == 2
    assert mock_api.async_get_hot_water_time_program.await_count == 2


async def test_failed_request_keeps_the_schedule(
    hass: HomeAssistant, config_entry, mock_api, freezer
) -> None:
    """A failed request keeps the last known schedule."""
    await setup_integration(hass, config_entry, mock_api)
    mock_api.async_get_heating_time_program.side_effect = ClientError("down")

    freezer.tick(timedelta(minutes=15))
    await refresh(hass, config_entry)

    schedule = clock_program(hass, CLIMATE_ZONE_ID, HEATING).attributes["schedule"]
    assert schedule["monday"][0] == {"time": "06:30", "mode": "Thuis", "setpoint": 20.0}


async def test_schedule_unknown_until_requested(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Without a clock program the schedule is unknown, the sensor still works."""
    mock_api.async_get_heating_time_program.side_effect = ClientError("down")
    await setup_integration(hass, config_entry, mock_api)

    state = clock_program(hass, CLIMATE_ZONE_ID, HEATING)
    assert state.state == "clock_program_1"
    assert state.attributes["schedule"] is None


def test_schedule_is_not_recorded() -> None:
    """The schedule is large and rarely changes, so it stays out of the database."""
    assert "schedule" in RemehaHomeClockProgramSensor._unrecorded_attributes


@pytest.mark.parametrize(
    "point",
    [
        {"day": 7, "time": "07:00", "activity": 1},
        {"day": "1", "time": "07:00", "activity": 1},
        {"day": 1, "time": None, "activity": 1},
        "not a switching point",
    ],
)
def test_invalid_switching_points_are_skipped(point) -> None:
    """Invalid switching points don't break the schedule."""
    schedule = heating_schedule({"switchPoints": [point]}, [])
    assert all(points == [] for points in schedule.values())


def test_unknown_activity() -> None:
    """An activity that isn't known has no name or setpoint."""
    schedule = heating_schedule(
        {"switchPoints": [{"day": 1, "time": "07:00", "activity": 9}]}, []
    )
    assert schedule["monday"] == [{"time": "07:00", "mode": None, "setpoint": None}]
