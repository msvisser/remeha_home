"""Fixtures for the Remeha Home tests.

The API responses in fixtures/ come from a Remeha Elga Ace hybrid (heat pump with a
gas boiler and a combi hot water zone), with the ids and names anonymized.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remeha_home.api import RemehaHomeAPI
from custom_components.remeha_home.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"

APPLIANCE_ID = "00000000-0000-0000-0000-00000000a001"
CLIMATE_ZONE_ID = "00000000-0000-0000-0000-00000000c001"
HOT_WATER_ZONE_ID = "00000000-0000-0000-0000-00000000d001"


def load_fixture(name: str):
    """Return the parsed JSON of a fixture file."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the integration from custom_components."""
    return


@pytest.fixture
def dashboard() -> dict:
    """Return the dashboard response. Tests can change it before or after setup."""
    return load_fixture("dashboard.json")


@pytest.fixture
def appliance(dashboard) -> dict:
    """Return the appliance of the dashboard."""
    return dashboard["appliances"][0]


@pytest.fixture
def climate_zone(appliance) -> dict:
    """Return the climate zone of the dashboard."""
    return appliance["climateZones"][0]


@pytest.fixture
def hot_water_zone(appliance) -> dict:
    """Return the hot water zone of the dashboard."""
    return appliance["hotWaterZones"][0]


@pytest.fixture
def mock_api(dashboard) -> MagicMock:
    """Return an API mock that answers with the fixtures."""
    api = MagicMock(spec=RemehaHomeAPI)
    api.async_get_dashboard = AsyncMock(side_effect=lambda: copy.deepcopy(dashboard))
    api.async_get_appliance_technical_information.return_value = load_fixture(
        "technical.json"
    )
    api.async_get_consumption_data_for_today.return_value = load_fixture(
        "consumption.json"
    )
    api.async_get_heating_curve.return_value = load_fixture("heating_curve.json")
    api.async_get_activities.return_value = load_fixture("activities.json")
    api.async_get_heating_time_program.return_value = load_fixture(
        "time_program_heating.json"
    )
    api.async_get_hot_water_time_program.return_value = load_fixture(
        "time_program_hot_water.json"
    )
    return api


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for the integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "token", "expires_at": 4102444800},
        },
    )


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Set up the integration with the API mock."""
    if hass.config_entries.async_get_entry(config_entry.entry_id) is None:
        config_entry.add_to_hass(hass)
    with (
        patch("custom_components.remeha_home.RemehaHomeAPI", return_value=mock_api),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow."
            "async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def refresh(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fetch the dashboard again and update the entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    await coordinator.async_refresh()
    await hass.async_block_till_done()


def entity_id(hass: HomeAssistant, platform: str, item_id: str, key: str) -> str | None:
    """Return the entity id for the unique id of an entity, or None."""
    return er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{DOMAIN}_{item_id}_{key}"
    )
