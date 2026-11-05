"""Test how the coordinator handles failing API requests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError, ClientResponseError, ClientTimeout
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
import pytest

from custom_components.remeha_home.api import REQUEST_TIMEOUT, RemehaHomeAPI
from custom_components.remeha_home.const import DOMAIN
from custom_components.remeha_home.coordinator import MAX_FAILED_UPDATES

from .conftest import refresh, setup_integration

CLIMATE = "climate.woonkamer"


def response_error(status: int) -> ClientResponseError:
    """Return the error aiohttp raises for an HTTP error status."""
    return ClientResponseError(
        MagicMock(), (), status=status, message="Internal Server Error"
    )


def coordinator(hass: HomeAssistant, config_entry):
    """Return the coordinator of the config entry."""
    return hass.data[DOMAIN][config_entry.entry_id]["coordinator"]


async def test_api_requests_have_a_timeout() -> None:
    """Every request has its own timeout, the shared session has none."""
    oauth_session = MagicMock()
    oauth_session.async_request = AsyncMock(return_value=MagicMock())
    api = RemehaHomeAPI(oauth_session)

    await api.async_set_manual("zone", 20.0)

    timeout = oauth_session.async_request.call_args.kwargs["timeout"]
    assert timeout == ClientTimeout(total=REQUEST_TIMEOUT)


@pytest.mark.parametrize(
    "error", [TimeoutError(), ClientConnectionError(), response_error(500)]
)
async def test_single_failed_update_keeps_the_previous_data(
    hass: HomeAssistant, config_entry, mock_api, dashboard, error
) -> None:
    """A single failed update keeps the entities available with their values."""
    await setup_integration(hass, config_entry, mock_api)
    state = hass.states.get(CLIMATE)

    mock_api.async_get_dashboard.side_effect = error
    await refresh(hass, config_entry)

    assert coordinator(hass, config_entry).last_update_success
    assert hass.states.get(CLIMATE).state == state.state
    assert hass.states.get(CLIMATE).attributes == state.attributes


async def test_repeated_failed_updates_make_the_entities_unavailable(
    hass: HomeAssistant, config_entry, mock_api, caplog
) -> None:
    """After several failed updates in a row, the entities become unavailable."""
    await setup_integration(hass, config_entry, mock_api)

    mock_api.async_get_dashboard.side_effect = response_error(500)
    for _ in range(MAX_FAILED_UPDATES - 1):
        await refresh(hass, config_entry)
        assert hass.states.get(CLIMATE).state != STATE_UNAVAILABLE

    await refresh(hass, config_entry)
    assert hass.states.get(CLIMATE).state == STATE_UNAVAILABLE
    # The log says why the update failed
    assert "500, Internal Server Error" in caplog.text


async def test_failed_update_count_resets_after_a_successful_update(
    hass: HomeAssistant, config_entry, mock_api, dashboard
) -> None:
    """Only failures in a row count."""
    await setup_integration(hass, config_entry, mock_api)
    succeed = mock_api.async_get_dashboard.side_effect

    for _ in range(2):
        mock_api.async_get_dashboard.side_effect = TimeoutError()
        for _ in range(MAX_FAILED_UPDATES - 1):
            await refresh(hass, config_entry)
        mock_api.async_get_dashboard.side_effect = succeed
        await refresh(hass, config_entry)

    assert hass.states.get(CLIMATE).state != STATE_UNAVAILABLE


async def test_failed_first_update_retries_the_setup(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Without previous data there is nothing to keep."""
    mock_api.async_get_dashboard.side_effect = TimeoutError()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unauthorized_update_starts_a_reauth(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """A 401 is not retried but starts a new login."""
    await setup_integration(hass, config_entry, mock_api)

    mock_api.async_get_dashboard.side_effect = response_error(401)
    await refresh(hass, config_entry)

    assert not coordinator(hass, config_entry).last_update_success
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


@pytest.mark.parametrize("error", [TimeoutError(), ClientConnectionError()])
@pytest.mark.parametrize(
    "request_name", ["async_get_heating_curve", "async_get_activities"]
)
async def test_optional_data_errors_dont_fail_the_update(
    hass: HomeAssistant, config_entry, mock_api, request_name, error
) -> None:
    """The heating curve and the activities are optional."""
    getattr(mock_api, request_name).side_effect = error
    await setup_integration(hass, config_entry, mock_api)

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(CLIMATE).state == "heat"
