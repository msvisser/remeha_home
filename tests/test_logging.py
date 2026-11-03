"""Test that the debug log doesn't contain personal data.

The bug report form asks for a debug log, so it must be safe to share, like the
diagnostics.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
import pytest

from custom_components.remeha_home.api import RemehaHomeAPI

from .conftest import load_fixture, setup_integration

SECRET = "Secret"
PERSONAL_KEYS = {"houseName", "name", "controlledZoneName", "serialNumber", "deviceIndex"}


def with_secrets(data):
    """Return the data with a recognizable value in every personal field."""
    if isinstance(data, dict):
        return {
            key: f"{SECRET} {key}"
            if key in PERSONAL_KEYS and not isinstance(value, (dict, list))
            else with_secrets(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [with_secrets(item) for item in data]
    return data


@pytest.fixture
def dashboard() -> dict:
    """Return the dashboard with personal data in it."""
    return with_secrets(load_fixture("dashboard.json"))


async def test_debug_log_has_no_personal_data(
    hass: HomeAssistant, config_entry, mock_api, caplog
) -> None:
    """The responses in the debug log are redacted like the diagnostics."""
    mock_api.async_get_appliance_technical_information.return_value = with_secrets(
        load_fixture("technical.json")
    )
    mock_api.async_get_consumption_data_for_today.return_value = with_secrets(
        load_fixture("consumption.json")
    )
    mock_api.async_get_activities.return_value = with_secrets(
        load_fixture("activities.json")
    )
    caplog.set_level(logging.DEBUG, logger="custom_components.remeha_home")

    await setup_integration(hass, config_entry, mock_api)

    assert "Requested dashboard information" in caplog.text
    assert "Requested technical information" in caplog.text
    assert "Requested activities data" in caplog.text
    assert "**REDACTED**" in caplog.text
    assert SECRET not in caplog.text


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("async_get_dashboard", ()),
        ("async_get_appliance_technical_information", ("appliance",)),
        ("async_get_consumption_data_for_today", ("appliance",)),
    ],
)
async def test_api_doesnt_log_the_responses(caplog, method, args) -> None:
    """The API client leaves logging the responses to the coordinator."""
    response = MagicMock()
    response.json = AsyncMock(return_value={"houseName": f"{SECRET} home"})
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(return_value=response)
    caplog.set_level(logging.DEBUG, logger="custom_components.remeha_home")

    await getattr(RemehaHomeAPI(oauth_session), method)(*args)

    assert SECRET not in caplog.text
