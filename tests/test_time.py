"""Test the parsing of Remeha times."""

from __future__ import annotations

from datetime import datetime

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import (
    APPLIANCE_ID,
    CLIMATE_ZONE_ID,
    HOT_WATER_ZONE_ID,
    entity_id,
    refresh,
    setup_integration,
)


@pytest.fixture(autouse=True)
async def amsterdam(hass: HomeAssistant) -> None:
    """Use the time zone of the fixtures, east of UTC."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")


@pytest.mark.parametrize(
    "value",
    [None, "", "0001-01-01T00:00:00Z", "0001-01-01T00:00:01Z", "not a time"],
)
async def test_remeha_time_not_set(hass: HomeAssistant, value) -> None:
    """Empty, unset and invalid times are None."""
    from custom_components.remeha_home.util import remeha_time

    assert remeha_time(value) is None


async def test_remeha_time_is_local(hass: HomeAssistant) -> None:
    """The API sends local times with a Z suffix."""
    from custom_components.remeha_home.util import remeha_time

    assert remeha_time("2026-10-22T22:00:00Z") == datetime(
        2026, 10, 22, 22, 0, tzinfo=dt_util.get_time_zone("Europe/Amsterdam")
    )


@pytest.mark.parametrize(
    "value",
    [None, "", "0001-01-01T00:00:00Z", "0001-01-01T00:00:01Z", "not a time"],
)
async def test_remeha_utc_time_not_set(hass: HomeAssistant, value) -> None:
    """Empty, unset and invalid UTC times are None."""
    from custom_components.remeha_home.util import remeha_utc_time

    assert remeha_utc_time(value) is None


async def test_remeha_utc_time(hass: HomeAssistant) -> None:
    """The boost end time and the end of an override are in UTC."""
    from custom_components.remeha_home.util import remeha_utc_time

    assert remeha_utc_time("2026-10-22T20:00:00Z") == datetime(
        2026, 10, 22, 20, 0, tzinfo=dt_util.UTC
    )
    assert remeha_utc_time("2026-10-22T13:11:59.2692621Z") == datetime(
        2026, 10, 22, 13, 11, 59, 269262, tzinfo=dt_util.UTC
    )


async def test_next_setpoint_time(hass: HomeAssistant, config_entry, mock_api) -> None:
    """The next setpoint times are local times."""
    await setup_integration(hass, config_entry, mock_api)

    # 22:00 and 23:00 in Amsterdam (CEST) are 20:00 and 21:00 UTC
    climate = entity_id(hass, "sensor", CLIMATE_ZONE_ID, "nextSwitchTime")
    assert hass.states.get(climate).state == "2026-10-22T20:00:00+00:00"
    hot_water = entity_id(hass, "sensor", HOT_WATER_ZONE_ID, "nextSwitchTime")
    assert hass.states.get(hot_water).state == "2026-10-22T21:00:00+00:00"


@pytest.mark.parametrize("value", [None, "0001-01-01T00:00:00Z"])
async def test_next_setpoint_time_not_set(
    hass: HomeAssistant, config_entry, mock_api, climate_zone, hot_water_zone, value
) -> None:
    """An unset next setpoint time is unknown, not an error or the year 1."""
    climate_zone["nextSwitchTime"] = value
    hot_water_zone["nextSwitchTime"] = value
    await setup_integration(hass, config_entry, mock_api)

    for item_id in (CLIMATE_ZONE_ID, HOT_WATER_ZONE_ID):
        state = hass.states.get(entity_id(hass, "sensor", item_id, "nextSwitchTime"))
        assert state.state == STATE_UNKNOWN


async def test_next_setpoint_time_becomes_unset(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """A time that becomes unset during operation turns unknown."""
    await setup_integration(hass, config_entry, mock_api)
    climate_zone["nextSwitchTime"] = "0001-01-01T00:00:00Z"
    await refresh(hass, config_entry)

    state = hass.states.get(entity_id(hass, "sensor", CLIMATE_ZONE_ID, "nextSwitchTime"))
    assert state.state == STATE_UNKNOWN


async def test_holiday_dates(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """The holiday sensor shows the scheduled dates."""
    appliance["holidaySchedule"] = {
        "startTime": "2027-01-11T00:00:01Z",
        "endTime": "2027-01-13T00:00:01Z",
        "active": False,
    }
    await setup_integration(hass, config_entry, mock_api)

    state = hass.states.get(
        entity_id(hass, "binary_sensor", APPLIANCE_ID, "holidaySchedule")
    )
    assert state.state == "off"
    assert state.attributes["start_date"] == "2027-01-11"
    assert state.attributes["end_date"] == "2027-01-13"


async def test_holiday_not_set(hass: HomeAssistant, config_entry, mock_api) -> None:
    """Without a holiday the dates are None."""
    await setup_integration(hass, config_entry, mock_api)

    state = hass.states.get(
        entity_id(hass, "binary_sensor", APPLIANCE_ID, "holidaySchedule")
    )
    assert state.state == "off"
    assert state.attributes["start_date"] is None
    assert state.attributes["end_date"] is None
