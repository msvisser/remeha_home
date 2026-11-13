"""Test the diagnostics download."""

from __future__ import annotations

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.remeha_home.const import DOMAIN

from .conftest import (
    APPLIANCE_ID,
    CLIMATE_ZONE_ID,
    HOT_WATER_ZONE_ID,
    load_fixture,
    setup_integration,
)

EMAIL = "user@example.com"
TOKEN = {
    "access_token": "secret-access-token",
    "refresh_token": "secret-refresh-token",
    "id_token": "secret-id-token",
    "token_type": "Bearer",
    "expires_at": 4102444800,
}


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry titled with the email address, like the config flow."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        data={"auth_implementation": DOMAIN, "token": TOKEN},
    )


def string_values(data) -> list[str]:
    """Return all strings in the data, without the keys."""
    if isinstance(data, dict):
        return [text for value in data.values() for text in string_values(value)]
    if isinstance(data, list):
        return [text for value in data for text in string_values(value)]
    return [data] if isinstance(data, str) else []


async def test_sections(
    hass: HomeAssistant, hass_client, config_entry, mock_api
) -> None:
    """The download holds the data that the integration uses."""
    await setup_integration(hass, config_entry, mock_api)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["entry"]["domain"] == DOMAIN
    appliance = diagnostics["dashboard"]["appliances"][0]
    assert appliance["applianceId"] == APPLIANCE_ID
    assert appliance["waterPressure"] == 1.7
    assert appliance["consumptionData"]["heatingEnergyConsumed"] == 5.0
    climate_zone = appliance["climateZones"][0]
    assert climate_zone["climateZoneId"] == CLIMATE_ZONE_ID
    assert climate_zone["heatingCurve"] == load_fixture("heating_curve.json")
    assert appliance["hotWaterZones"][0]["hotWaterZoneId"] == HOT_WATER_ZONE_ID

    technical_info = diagnostics["technical_info"][APPLIANCE_ID]
    assert technical_info["applianceName"] == "Elga Ace"
    gateway = technical_info["internetConnectedGateways"][0]
    assert gateway["softwareVersion"] == "2.28.6"

    activities = diagnostics["activities"][CLIMATE_ZONE_ID]
    assert [
        (activity["type"], activity["activityNumber"], activity["temperature"])
        for activity in activities
    ] == [
        (activity["type"], activity["activityNumber"], activity["temperature"])
        for activity in load_fixture("activities.json")
    ]


async def test_personal_data_redacted(
    hass: HomeAssistant, hass_client, config_entry, mock_api
) -> None:
    """The login, the names typed in the app and the serial numbers are left out."""
    technical = load_fixture("technical.json")
    technical["internetConnectedGateways"][0]["controlledZoneName"] = "Woonkamer"
    mock_api.async_get_appliance_technical_information.return_value = technical
    await setup_integration(hass, config_entry, mock_api)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics["entry"]["title"] == REDACTED
    assert diagnostics["entry"]["data"]["token"] == REDACTED
    appliance = diagnostics["dashboard"]["appliances"][0]
    assert appliance["houseName"] == REDACTED
    assert appliance["climateZones"][0]["name"] == REDACTED
    assert appliance["hotWaterZones"][0]["name"] == REDACTED
    statistics = appliance["consumptionData"]["producerPerformanceStatistics"]
    assert {producer["deviceIndex"] for producer in statistics["producers"]} == {
        REDACTED
    }
    technical_info = diagnostics["technical_info"][APPLIANCE_ID]
    gateway = technical_info["internetConnectedGateways"][0]
    assert gateway["name"] == REDACTED
    assert gateway["serialNumber"] == REDACTED
    assert gateway["controlledZoneName"] == REDACTED
    activities = diagnostics["activities"][CLIMATE_ZONE_ID]
    assert {activity["name"] for activity in activities} == {REDACTED}

    values = string_values(diagnostics)
    for private in (
        EMAIL,
        TOKEN["access_token"],
        TOKEN["refresh_token"],
        TOKEN["id_token"],
        "Home",
        "Woonkamer",
        "00000000",
        "000000000000",
        "Thuis",
        "Werken",
    ):
        assert private not in values, private

    # The data of the integration itself is not changed
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    assert coordinator.data["appliances"][0]["houseName"] == "Home"
