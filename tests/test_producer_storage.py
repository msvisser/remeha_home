"""Test persistence and migration of energy producer identifiers."""

from __future__ import annotations

from datetime import timedelta
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.remeha_home import (
    legacy_producer_ids_storage_key,
    producer_ids_storage_key,
)
from custom_components.remeha_home.const import DOMAIN

from .conftest import APPLIANCE_ID, setup_integration


async def flush_delayed_save(hass: HomeAssistant, freezer) -> None:
    """Let Store.async_delay_save write its pending data."""
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_new_assignments_use_delayed_save_and_dotted_key(
    hass: HomeAssistant, config_entry, mock_api, hass_storage, freezer
) -> None:
    """Producer IDs are stored under the same key style as holiday modes."""
    await setup_integration(hass, config_entry, mock_api)
    await flush_delayed_save(hass, freezer)

    key = producer_ids_storage_key(config_entry)
    assert key == f"{DOMAIN}.{config_entry.entry_id}.producer_ids"
    assert len(hass_storage[key]["data"]) == 2
    assert legacy_producer_ids_storage_key(config_entry) not in hass_storage


async def test_old_assignments_are_migrated_without_changing_device_ids(
    hass: HomeAssistant, config_entry, mock_api, hass_storage, freezer
) -> None:
    """Existing preview users retain their saved producer IDs on upgrade."""
    old_key = legacy_producer_ids_storage_key(config_entry)
    boiler_identity = json.dumps(
        [APPLIANCE_ID, 2, "GasBoiler", "NaturalGas"], separators=(",", ":")
    )
    saved = {boiler_identity: f"{APPLIANCE_ID}_2_GasBoiler"}
    await Store(hass, 1, old_key).async_save(saved)

    await setup_integration(hass, config_entry, mock_api)

    resolver = hass.data[DOMAIN][config_entry.entry_id]["coordinator"].producer_id_resolver
    assert resolver.assignments[boiler_identity] == f"{APPLIANCE_ID}_2_GasBoiler"
    await flush_delayed_save(hass, freezer)
    new_key = producer_ids_storage_key(config_entry)
    assert hass_storage[new_key]["data"][boiler_identity] == saved[boiler_identity]

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert new_key not in hass_storage
    assert old_key not in hass_storage
