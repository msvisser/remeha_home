"""Test the devices that the integration registers."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.remeha_home.const import DOMAIN
from custom_components.remeha_home.producer_ids import ProducerIdResolver

from .conftest import (
    APPLIANCE_ID,
    CLIMATE_ZONE_ID,
    HOT_WATER_ZONE_ID,
    entity_id,
    load_fixture,
    refresh,
    setup_integration,
)


async def test_devices_linked_to_appliance(
    hass: HomeAssistant, config_entry, mock_api, caplog
) -> None:
    """Link the zones and the producers to the appliance by its device id."""
    await setup_integration(hass, config_entry, mock_api)

    registry = dr.async_get(hass)
    appliance = registry.async_get_device_by_identifier(
        (DOMAIN, APPLIANCE_ID), config_entry.entry_id
    )
    assert appliance is not None
    assert appliance.via_device_id is None

    children = [
        device
        for device in dr.async_entries_for_config_entry(registry, config_entry.entry_id)
        if device.id != appliance.id
    ]
    child_ids = {item_id for device in children for _, item_id in device.identifiers}
    assert {CLIMATE_ZONE_ID, HOT_WATER_ZONE_ID} <= child_ids
    # The climate zone, the hot water zone, the heat pump and the gas boiler
    assert len(children) == 4
    assert all(device.via_device_id == appliance.id for device in children)
    # On the maintainer's Elga Ace these instances do not collide. Their
    # original unique IDs must survive an integration upgrade unchanged.
    assert {f"{APPLIANCE_ID}_1", f"{APPLIANCE_ID}_2"} <= child_ids
    assert f"{APPLIANCE_ID}_2_GasBoiler" not in child_ids
    assert entity_id(hass, "sensor", f"{APPLIANCE_ID}_2", "energyConsumptionCH")

    # Home Assistant 2027.8 no longer accepts the deprecated via_device
    assert "deprecated `via_device`" not in caplog.text


async def test_hybrid_producers_with_same_instance_keep_separate_devices_and_energy(
    hass: HomeAssistant, config_entry, mock_api, appliance
) -> None:
    """Elga Ace can report instance 1 for both its heat pump and gas boiler."""
    consumption = mock_api.async_get_consumption_data_for_today.return_value["data"][0]
    heat_pump, boiler = consumption["producerPerformanceStatistics"]["producers"]
    boiler["instanceWithinDevice"] = heat_pump["instanceWithinDevice"]

    await setup_integration(hass, config_entry, mock_api)

    resolver = hass.data[DOMAIN][config_entry.entry_id]["coordinator"].producer_id_resolver
    heat_pump_id = resolver.get_id(APPLIANCE_ID, heat_pump)
    boiler_id = resolver.get_id(APPLIANCE_ID, boiler)
    assert heat_pump_id != boiler_id

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    assert coordinator.get_by_id(heat_pump_id)["producerType"] == "HeatPumpAirSource"
    assert coordinator.get_by_id(boiler_id)["producerType"] == "GasBoiler"

    registry = dr.async_get(hass)
    pump_device = registry.async_get_device_by_identifier(
        (DOMAIN, heat_pump_id), config_entry.entry_id
    )
    boiler_device = registry.async_get_device_by_identifier(
        (DOMAIN, boiler_id), config_entry.entry_id
    )
    assert pump_device is not None and boiler_device is not None
    assert pump_device.id != boiler_device.id

    pump_entity = entity_id(hass, "sensor", heat_pump_id, "energyConsumptionCH")
    boiler_entity = entity_id(hass, "sensor", boiler_id, "energyConsumptionCH")
    assert pump_entity is not None and boiler_entity is not None
    assert float(hass.states.get(pump_entity).state) == 4.0
    assert float(hass.states.get(boiler_entity).state) == round(
        1.0 / appliance["gasCalorificValue"], 2
    )
    assert hass.states.get(pump_entity).attributes["unit_of_measurement"] == "kWh"
    assert hass.states.get(boiler_entity).attributes["unit_of_measurement"] == "m³"


async def test_real_hybrid_collision_diagnostics_fixture(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Use the anonymized producer data from an affected Elga Ace All-in-One."""
    consumption = mock_api.async_get_consumption_data_for_today.return_value["data"][0]
    consumption.update(load_fixture("hybrid_same_instance.json"))

    await setup_integration(hass, config_entry, mock_api)

    registry = dr.async_get(hass)
    for producer_id in (f"{APPLIANCE_ID}_1", f"{APPLIANCE_ID}_1_GasBoiler"):
        assert registry.async_get_device_by_identifier(
            (DOMAIN, producer_id), config_entry.entry_id
        ) is not None

    pump_sensor = entity_id(hass, "sensor", f"{APPLIANCE_ID}_1", "energyConsumptionCH")
    gas_sensor = entity_id(
        hass, "sensor", f"{APPLIANCE_ID}_1_GasBoiler", "energyConsumptionCH"
    )
    assert pump_sensor is not None and gas_sensor is not None
    assert float(hass.states.get(pump_sensor).state) == 3.6
    assert hass.states.get(pump_sensor).attributes["unit_of_measurement"] == "kWh"
    assert hass.states.get(gas_sensor).attributes["unit_of_measurement"] == "m³"


def test_producer_ids_remain_unchanged_without_collisions() -> None:
    """Stand-alone, conventional hybrid and multi-producer IDs remain stable."""
    heat_pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    boiler = {
        "producerType": "GasBoiler",
        "energyType": "NaturalGas",
        "instanceWithinDevice": 2,
    }
    resolver = ProducerIdResolver()
    assert resolver.resolve(APPLIANCE_ID, [heat_pump])[0][0][1] == f"{APPLIANCE_ID}_1"
    assert resolver.resolve(APPLIANCE_ID, [boiler])[0][0][1] == f"{APPLIANCE_ID}_2"
    assert resolver.resolve(APPLIANCE_ID, [heat_pump, boiler])[0][0][1] == f"{APPLIANCE_ID}_1"
    assert resolver.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_2"
    # The appliance type must not force a suffix when its instances differ.
    fresh = ProducerIdResolver()
    fresh.resolve(APPLIANCE_ID, [heat_pump, boiler], appliance_type="HeatPump")
    assert fresh.get_id(APPLIANCE_ID, heat_pump) == f"{APPLIANCE_ID}_1"
    assert fresh.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_2"
    gas_first = ProducerIdResolver()
    gas_first.resolve(APPLIANCE_ID, [boiler], appliance_type="HeatPump")
    assert gas_first.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_2"


def test_colliding_ids_do_not_depend_on_api_producer_order() -> None:
    """An Elga hybrid with duplicated instance indexes is deterministic."""
    heat_pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    boiler = {
        "producerType": "GasBoiler",
        "energyType": "NaturalGas",
        "instanceWithinDevice": 1,
    }
    for producers in ([heat_pump, boiler], [boiler, heat_pump]):
        resolver = ProducerIdResolver()
        resolver.resolve(APPLIANCE_ID, producers)
        assert resolver.get_id(APPLIANCE_ID, heat_pump) == f"{APPLIANCE_ID}_1"
        assert resolver.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_1_GasBoiler"


def test_persistent_producer_ids_survive_missing_producers_and_restart() -> None:
    """Once assigned, producer IDs do not depend on later incomplete API data."""
    heat_pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    boiler = {
        "producerType": "GasBoiler",
        "energyType": "NaturalGas",
        "instanceWithinDevice": 1,
    }
    resolver = ProducerIdResolver()
    first, changed = resolver.resolve(APPLIANCE_ID, [heat_pump, boiler])
    assert changed
    assert {item["producerType"]: uid for item, uid in first} == {
        "HeatPumpAirSource": f"{APPLIANCE_ID}_1",
        "GasBoiler": f"{APPLIANCE_ID}_1_GasBoiler",
    }
    previous = resolver.get_id(APPLIANCE_ID, boiler)
    only_boiler, changed = resolver.resolve(APPLIANCE_ID, [boiler])
    assert not changed
    assert only_boiler[0][1] == previous

    restored = ProducerIdResolver(resolver.assignments)
    assert restored.resolve(APPLIANCE_ID, [boiler])[0][0][1] == previous
    restored.resolve(APPLIANCE_ID, [boiler, heat_pump])
    assert restored.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_1_GasBoiler"
    assert restored.get_id(APPLIANCE_ID, heat_pump) == f"{APPLIANCE_ID}_1"


def test_standalone_and_incomplete_initial_discovery_preserve_ids() -> None:
    """A standalone device retains its legacy ID; later producers get new IDs."""
    heat_pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    boiler = {
        "producerType": "GasBoiler",
        "energyType": "NaturalGas",
        "instanceWithinDevice": 1,
    }
    resolver = ProducerIdResolver()
    assert resolver.resolve(APPLIANCE_ID, [boiler])[0][0][1] == f"{APPLIANCE_ID}_1"
    resolver.resolve(APPLIANCE_ID, [heat_pump, boiler])
    assert resolver.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_1"
    assert resolver.get_id(APPLIANCE_ID, heat_pump) == f"{APPLIANCE_ID}_1_HeatPumpAirSource"


def test_ambiguous_same_type_duplicate_producers_are_not_merged() -> None:
    """Skip indistinguishable API producers rather than mix their meter values."""
    heat_pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    resolver = ProducerIdResolver()
    allocated, changed = resolver.resolve(APPLIANCE_ID, [heat_pump, dict(heat_pump)])
    assert allocated == []
    assert not changed


def test_hybrid_first_reports_only_boiler() -> None:
    """Only a real collision or a registered electric entity reserves an ID."""
    boiler = {
        "producerType": "GasBoiler",
        "energyType": "NaturalGas",
        "instanceWithinDevice": 1,
    }
    pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    resolver = ProducerIdResolver()
    assert resolver.resolve(
        APPLIANCE_ID, [boiler], appliance_type="HeatPump"
    )[0][0][1] == f"{APPLIANCE_ID}_1"
    restored = ProducerIdResolver(resolver.assignments)
    restored.resolve(APPLIANCE_ID, [pump, boiler], appliance_type="HeatPump")
    assert restored.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_1"
    assert restored.get_id(APPLIANCE_ID, pump) == f"{APPLIANCE_ID}_1_HeatPumpAirSource"


def test_boiler_only_preserves_a_registered_electric_legacy_id() -> None:
    """A gas-only response must not steal an electric entity's legacy ID."""
    boiler = {
        "producerType": "GasBoiler",
        "energyType": "NaturalGas",
        "instanceWithinDevice": 1,
    }
    resolver = ProducerIdResolver()
    resolver.resolve(
        APPLIANCE_ID,
        [boiler],
        appliance_type="HeatPump",
        existing_electric_legacy_ids={f"{APPLIANCE_ID}_1"},
    )
    assert resolver.get_id(APPLIANCE_ID, boiler) == f"{APPLIANCE_ID}_1_GasBoiler"


async def test_boiler_only_checks_electric_entity_registry(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Reserve a legacy ID only if a heat pump previously registered it."""
    consumption = mock_api.async_get_consumption_data_for_today.return_value["data"][0]
    boiler = consumption["producerPerformanceStatistics"]["producers"][1]
    boiler["instanceWithinDevice"] = 1
    consumption["producerPerformanceStatistics"]["producers"] = [boiler]
    config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DOMAIN}_{APPLIANCE_ID}_1_seasonalEfficiency",
        config_entry=config_entry,
    )

    await setup_integration(hass, config_entry, mock_api)

    registry = dr.async_get(hass)
    assert registry.async_get_device_by_identifier(
        (DOMAIN, f"{APPLIANCE_ID}_1_GasBoiler"), config_entry.entry_id
    ) is not None
    assert entity_id(
        hass, "sensor", f"{APPLIANCE_ID}_1_GasBoiler", "energyConsumptionCH"
    ) is not None


async def test_incomplete_producers_do_not_create_unnamed_devices(
    hass: HomeAssistant, config_entry, mock_api, caplog
) -> None:
    """Null producer fields must never create an appliance_None device."""
    consumption = mock_api.async_get_consumption_data_for_today.return_value["data"][0]
    producers = consumption["producerPerformanceStatistics"]["producers"]
    missing = {
        "instanceWithinDevice": None,
        "producerType": None,
        "energyType": None,
    }
    producers.append(missing)
    caplog.set_level(logging.DEBUG, logger="custom_components.remeha_home.producer_ids")
    await setup_integration(hass, config_entry, mock_api)

    registry = dr.async_get(hass)
    assert registry.async_get_device_by_identifier(
        (DOMAIN, f"{APPLIANCE_ID}_None"), config_entry.entry_id
    ) is None
    assert entity_id(hass, "sensor", f"{APPLIANCE_ID}_None", "seasonalEfficiency") is None
    resolver = hass.data[DOMAIN][config_entry.entry_id]["coordinator"].producer_id_resolver
    assert resolver.get_id(APPLIANCE_ID, missing) is None
    assert all("null" not in identity for identity in resolver.assignments)

    # The API later stops reporting the placeholder. Valid producer IDs persist.
    producers.remove(missing)
    await refresh(hass, config_entry)
    assert entity_id(hass, "sensor", f"{APPLIANCE_ID}_1", "seasonalEfficiency")
    debug_logs = [
        record
        for record in caplog.records
        if record.levelno == logging.DEBUG
        and "Ignoring incomplete energy producer records" in record.message
    ]
    assert len(debug_logs) == 1


def test_indistinguishable_producer_warning_is_logged_once(caplog) -> None:
    """Refreshes must not emit the same ambiguity warning every 15 minutes."""
    pump = {
        "producerType": "HeatPumpAirSource",
        "energyType": "Electric",
        "instanceWithinDevice": 1,
    }
    resolver = ProducerIdResolver()
    for _ in range(3):
        resolved, _ = resolver.resolve(APPLIANCE_ID, [pump, dict(pump)])
        assert resolved == []
    warnings = [
        record
        for record in caplog.records
        if "Multiple indistinguishable producers" in record.message
    ]
    assert len(warnings) == 1
