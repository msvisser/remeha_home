"""Test the action that overrides the clock program for a while."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import voluptuous as vol

from custom_components.remeha_home.api import RemehaHomeAPI
from custom_components.remeha_home.const import DOMAIN

from .conftest import CLIMATE_ZONE_ID, setup_integration

CLIMATE = "climate.woonkamer"
NOW = datetime(2026, 11, 8, 11, 12, 25, 123456, tzinfo=UTC)


async def set_override(hass: HomeAssistant, **data) -> None:
    """Call the action on the climate zone."""
    await hass.services.async_call(
        DOMAIN,
        "set_temporary_override",
        {ATTR_ENTITY_ID: CLIMATE, **data},
        blocking=True,
    )


@pytest.fixture
def scheduling(climate_zone: dict) -> dict:
    """Let the zone follow the clock program."""
    climate_zone["zoneMode"] = "Scheduling"
    return climate_zone


async def test_override_with_end_time(
    hass: HomeAssistant,
    config_entry,
    mock_api,
    scheduling,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The override is sent with the end time, and the data is refreshed."""
    freezer.move_to(NOW)
    await setup_integration(hass, config_entry, mock_api)
    calls = mock_api.async_get_dashboard.await_count

    await set_override(hass, temperature=21, duration="01:30:00")

    mock_api.async_set_temporary_override.assert_awaited_once_with(
        CLIMATE_ZONE_ID, 21.0, datetime(2026, 11, 8, 12, 42, 25, tzinfo=UTC)
    )
    await hass.async_block_till_done()
    assert mock_api.async_get_dashboard.await_count > calls


async def test_override_in_temporary_override(
    hass: HomeAssistant, config_entry, mock_api, climate_zone
) -> None:
    """An override can replace a running override."""
    climate_zone["zoneMode"] = "TemporaryOverride"
    await setup_integration(hass, config_entry, mock_api)

    await set_override(hass, temperature=19.5, duration={"minutes": 20})

    mock_api.async_set_temporary_override.assert_awaited_once()


@pytest.mark.parametrize("zone_mode", ["Manual", "FrostProtection"])
async def test_requires_auto(
    hass: HomeAssistant, config_entry, mock_api, climate_zone, zone_mode
) -> None:
    """Outside auto mode the action asks to set the zone to auto first."""
    climate_zone["zoneMode"] = zone_mode
    await setup_integration(hass, config_entry, mock_api)

    with pytest.raises(ServiceValidationError) as error:
        await set_override(hass, temperature=21, duration="01:00:00")

    assert error.value.translation_key == "temporary_override_requires_auto"
    assert error.value.translation_placeholders == {"entity_id": CLIMATE}
    mock_api.async_set_temporary_override.assert_not_awaited()


async def test_requires_end_time_capability(
    hass: HomeAssistant, config_entry, mock_api, scheduling
) -> None:
    """A zone without the end time capability gets a clear error."""
    scheduling["capabilityTemporaryOverrideEndTime"] = False
    await setup_integration(hass, config_entry, mock_api)

    with pytest.raises(ServiceValidationError) as error:
        await set_override(hass, temperature=21, duration="01:00:00")

    assert error.value.translation_key == "temporary_override_not_supported"
    mock_api.async_set_temporary_override.assert_not_awaited()


@pytest.mark.parametrize("temperature", [4.5, 30.5])
async def test_temperature_out_of_range(
    hass: HomeAssistant, config_entry, mock_api, scheduling, temperature
) -> None:
    """The temperature must be within the range of the zone."""
    await setup_integration(hass, config_entry, mock_api)

    with pytest.raises(ServiceValidationError) as error:
        await set_override(hass, temperature=temperature, duration="01:00:00")

    assert error.value.translation_key == "temperature_out_of_range"
    mock_api.async_set_temporary_override.assert_not_awaited()


@pytest.mark.parametrize("duration", ["00:00:30", "00:00:00", {"days": 7, "minutes": 1}])
async def test_duration_out_of_range(
    hass: HomeAssistant, config_entry, mock_api, scheduling, duration
) -> None:
    """The duration must be between 1 minute and 7 days."""
    await setup_integration(hass, config_entry, mock_api)

    with pytest.raises(vol.Invalid):
        await set_override(hass, temperature=21, duration=duration)

    mock_api.async_set_temporary_override.assert_not_awaited()


async def test_api_failure_is_raised(
    hass: HomeAssistant, config_entry, mock_api, scheduling
) -> None:
    """A failed request reaches the caller."""
    await setup_integration(hass, config_entry, mock_api)
    mock_api.async_set_temporary_override.side_effect = RuntimeError("refused")

    with pytest.raises(RuntimeError):
        await set_override(hass, temperature=21, duration="01:00:00")


@pytest.mark.parametrize(
    ("end_time", "payload"),
    [
        (
            datetime(2026, 11, 8, 13, 22, tzinfo=timezone(timedelta(hours=1))),
            {"roomTemperatureSetPoint": 21.0, "endTime": "2026-11-08T12:22:00Z"},
        ),
        (None, {"roomTemperatureSetPoint": 21.0}),
    ],
)
async def test_api_sends_end_time_in_utc(end_time, payload) -> None:
    """The end time is sent in UTC with a Z, like the API reports it.

    Without an end time the request is the same as before: the override lasts until
    the next switch of the clock program.
    """
    session = MagicMock()
    session.async_request = AsyncMock(return_value=MagicMock())
    api = RemehaHomeAPI(session)

    await api.async_set_temporary_override("zone", 21.0, end_time)

    session.async_request.assert_awaited_once()
    args, kwargs = session.async_request.await_args
    assert args[1].endswith("/climate-zones/zone/modes/temporary-override")
    assert kwargs["json"] == payload
