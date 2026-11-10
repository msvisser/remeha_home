"""Test the activity temperature numbers."""

from __future__ import annotations

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from custom_components.remeha_home.const import DOMAIN

from .conftest import CLIMATE_ZONE_ID, entity_id, load_fixture, setup_integration


def activity_number(hass: HomeAssistant, number: int) -> str:
    """Return the entity id of the temperature of a heating activity."""
    return entity_id(hass, "number", CLIMATE_ZONE_ID, f"activity_{number}_temperature")


async def set_value(hass: HomeAssistant, entity: str, value: float) -> None:
    """Set a number entity."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity, ATTR_VALUE: value},
        blocking=True,
    )


def heating_temperatures(payload: list[dict]) -> dict[int, float]:
    """Return the temperatures of an activities payload by activity number."""
    return {item["activityNumber"]: item["temperature"] for item in payload}


async def test_second_write_keeps_the_first(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """A write is built from what was written before, not from a read that lags behind.

    The read right after a write has answered with the values from before it; a write
    built from that read sends those old values back for the activities it did not
    change.
    """
    await setup_integration(hass, config_entry, mock_api)
    # Every later read answers with the values from before any write
    mock_api.async_get_activities.return_value = load_fixture("activities.json")

    await set_value(hass, activity_number(hass, 1), 21.0)
    await set_value(hass, activity_number(hass, 5), 22.0)

    first, second = (
        call.args[1] for call in mock_api.async_set_heating_activities.await_args_list
    )
    assert heating_temperatures(first) == {1: 21.0, 2: 20.0, 3: 19.0, 4: 16.5, 5: 20.0}
    assert heating_temperatures(second) == {1: 21.0, 2: 20.0, 3: 19.0, 4: 16.5, 5: 22.0}
    assert hass.states.get(activity_number(hass, 1)).state == "21.0"
    assert hass.states.get(activity_number(hass, 5)).state == "22.0"


async def test_cooling_activities_are_kept(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Only the heating temperatures change; the Cooling activities stay as they were."""
    await setup_integration(hass, config_entry, mock_api)

    await set_value(hass, activity_number(hass, 2), 18.0)

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    activities = coordinator.get_activities(CLIMATE_ZONE_ID)
    cooling = [a for a in activities if a["type"] == "Cooling"]
    assert cooling == [
        a for a in load_fixture("activities.json") if a["type"] == "Cooling"
    ]
    assert [
        (a["activityNumber"], a["temperature"])
        for a in activities
        if a["type"] == "Heating"
    ] == [(1, 20.0), (2, 18.0), (3, 19.0), (4, 16.5), (5, 20.0)]
