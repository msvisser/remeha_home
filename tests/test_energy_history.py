"""Read-only historical energy action and hybrid-producer normalization."""

from __future__ import annotations

import copy
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import pytest

from custom_components.remeha_home.api import RemehaHomeAPI
from custom_components.remeha_home.const import DOMAIN
from custom_components.remeha_home.energy_history import (
    combine_history,
    history_batches,
    normalize_history_day,
)
from custom_components.remeha_home.energy_history_service import (
    SERVICE_GET_ENERGY_HISTORY,
)

from .conftest import APPLIANCE_ID, load_fixture, setup_integration


def _january_9() -> dict:
    """Make a historical Elga Ace hybrid response with app screenshot values."""
    item = copy.deepcopy(load_fixture("consumption.json")["data"][0])
    item["timeStamp"] = "2026-01-09T00:00:00+00:00"
    item["heatingEnergyConsumed"] = 20.0  # includes gas; NOT the HP input
    item["heatingEnergyDelivered"] = 68.0
    producers = item["producerPerformanceStatistics"]["producers"]
    producers[0]["energyConsumptionCH"] = 18.0
    producers[0]["energyProductionCH"] = 68.0
    producers[1]["energyConsumptionCH"] = 2.0
    producers[1]["energyProductionCH"] = None
    # A broken, unnamed hybrid producer like one observed in Remeha diagnostics.
    producers.append(
        {"instanceWithinDevice": None, "producerType": None, "energyType": None}
    )
    return item


def test_normalize_hybrid_and_cop() -> None:
    """Calculate day COP from the heat-pump producer, never mixed totals."""
    row = normalize_history_day(_january_9())
    assert row is not None
    assert row["date"] == "2026-01-09"
    assert row["heat_pump_heating_consumed_kwh"] == 18.0
    assert row["heat_pump_heating_delivered_kwh"] == 68.0
    assert row["heat_pump_heating_cop"] == pytest.approx(68 / 18)
    assert row["gas_heating_consumed_kwh"] == 2.0
    assert len(row["producers"]) == 2
    assert all("instance_within_device" not in row for row in row["producers"])


def test_incomplete_identified_heat_pump_makes_total_unknown() -> None:
    """Never report a partial sum if a recognizable producer has no instance."""
    item = _january_9()
    item["producerPerformanceStatistics"]["producers"].append(
        {
            "instanceWithinDevice": None,
            "producerType": "HeatPumpAirSource",
            "energyType": "Electric",
            "energyConsumptionCH": 3.0,
            "energyProductionCH": 12.0,
        }
    )
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] is None
    assert row["heat_pump_heating_delivered_kwh"] is None
    assert row["heat_pump_heating_cop"] is None
    assert row["gas_heating_consumed_kwh"] == 2.0
    assert len(row["producers"]) == 2


def test_duplicate_heat_pump_records_are_not_double_counted() -> None:
    """Duplicated API producers must not double the historical energy totals."""
    item = _january_9()
    producers = item["producerPerformanceStatistics"]["producers"]
    producers.append(copy.deepcopy(producers[0]))
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] is None
    assert row["heat_pump_heating_delivered_kwh"] is None
    assert row["heat_pump_heating_cop"] is None
    assert row["gas_heating_consumed_kwh"] == 2.0
    assert len(row["producers"]) == 1


def test_duplicate_gas_producer_only_invalidates_gas() -> None:
    """Ambiguous boiler measurements must not hide valid heat-pump energy."""
    item = _january_9()
    producers = item["producerPerformanceStatistics"]["producers"]
    producers.append(copy.deepcopy(producers[1]))
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] == 18.0
    assert row["heat_pump_heating_delivered_kwh"] == 68.0
    assert row["gas_heating_consumed_kwh"] is None


def test_shared_instance_and_distinct_pumps_remain_valid() -> None:
    """A hybrid collision is valid, as are multiple distinct heat pumps."""
    item = _january_9()
    producers = item["producerPerformanceStatistics"]["producers"]
    producers[1]["instanceWithinDevice"] = 1
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] == 18.0
    assert row["gas_heating_consumed_kwh"] == 2.0

    extra_pump = copy.deepcopy(producers[0])
    extra_pump["instanceWithinDevice"] = "3"
    extra_pump["energyConsumptionCH"] = 1.0
    extra_pump["energyProductionCH"] = 4.0
    producers.append(extra_pump)
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] == 19.0
    assert row["heat_pump_heating_delivered_kwh"] == 72.0
    assert row["heat_pump_heating_cop"] == pytest.approx(72 / 19)


def test_malformed_performance_statistics_remain_unknown() -> None:
    """Malformed API structures must not break the action."""
    item = _january_9()
    item["producerPerformanceStatistics"] = []
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] is None
    assert row["gas_heating_consumed_kwh"] is None


def test_completed_daily_history_across_dst_matches_observed_action_values() -> None:
    """Regression for five days observed through HA's action, not a raw fixture."""
    expected = [
        ("2026-10-23", 5.2, 24.8),
        ("2026-10-24", 6.3, 29.8),
        ("2026-10-25", 5.5, 24.8),
        ("2026-10-26", 7.0, 30.8),
        ("2026-10-27", 1.7, 9.3),
    ]
    raw_days = []
    for day, consumed, delivered in expected:
        item = _january_9()
        item["timeStamp"] = f"{day}T00:00:00+00:00"
        producers = item["producerPerformanceStatistics"]["producers"]
        producers[0]["energyConsumptionCH"] = consumed
        producers[0]["energyProductionCH"] = delivered
        producers[1]["energyConsumptionCH"] = 0.0
        raw_days.append(item)

    result = combine_history(
        date(2026, 10, 23), date(2026, 10, 27), [{"data": raw_days}]
    )
    assert result["missing_dates"] == []
    for row, (day, consumed, delivered) in zip(
        result["days"], expected, strict=True
    ):
        assert row["date"] == day
        assert row["heat_pump_heating_consumed_kwh"] == consumed
        assert row["heat_pump_heating_delivered_kwh"] == delivered
        assert row["heat_pump_heating_cop"] == round(delivered / consumed, 2)
        assert row["gas_heating_consumed_kwh"] == 0.0


def test_missing_heat_pump_is_unknown_not_zero() -> None:
    """Never substitute appliance totals if the heat-pump fields are absent."""
    item = _january_9()
    item["producerPerformanceStatistics"] = {"producers": []}
    row = normalize_history_day(item)
    assert row["heat_pump_heating_consumed_kwh"] is None
    assert row["heat_pump_heating_delivered_kwh"] is None
    assert row["heat_pump_heating_cop"] is None
    assert row["gas_heating_consumed_kwh"] is None


def test_invalid_and_zero_energy_no_cop() -> None:
    """Missing output, invalid input, and zero input are not divided through."""
    for consumed, delivered in ((0, 5), (None, 5), ("NaN", 5), (2, None)):
        item = _january_9()
        producer = item["producerPerformanceStatistics"]["producers"][0]
        producer["energyConsumptionCH"] = consumed
        producer["energyProductionCH"] = delivered
        assert normalize_history_day(item)["heat_pump_heating_cop"] is None


def test_empty_history_and_duplicate_guard() -> None:
    """Unreported and conflicting dates remain missing without failing the action."""
    start, end = date(2026, 1, 9), date(2026, 1, 10)
    result = combine_history(start, end, [{"data": [_january_9()]}])
    assert result["missing_dates"] == ["2026-01-10"]
    assert len(result["days"]) == 1
    assert result["period"]["complete"] is False
    assert result["period"]["heat_pump_heating_cop"] == round(68 / 18, 2)

    altered = _january_9()
    altered["producerPerformanceStatistics"]["producers"][0]["energyConsumptionCH"] = (
        17.0
    )
    result = combine_history(
        start, end, [{"data": [_january_9(), altered, _january_9()]}]
    )
    assert result["days"] == []
    assert result["missing_dates"] == ["2026-01-09", "2026-01-10"]
    assert result["period"]["complete"] is False
    assert result["period"]["heat_pump_heating_cop"] is None


def test_history_batches() -> None:
    """Split in 31-day windows and do not allow unbounded API reads."""
    assert list(history_batches(date(2026, 1, 1), date(2026, 2, 5))) == [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 5)),
    ]
    with pytest.raises(ValueError, match="End date"):
        list(history_batches(date(2026, 2, 1), date(2026, 1, 1)))
    with pytest.raises(ValueError, match="366"):
        list(history_batches(date(2026, 1, 1), date(2027, 1, 2)))


async def test_api_date_range_uses_oauth() -> None:
    """Use the existing authenticated session; never create new credentials."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value={"data": []})
    oauth = MagicMock()
    oauth.async_request = AsyncMock(return_value=response)
    api = RemehaHomeAPI(oauth)

    assert await api.async_get_consumption_data_for_range(
        APPLIANCE_ID, date(2026, 1, 9), date(2026, 1, 10)
    ) == {"data": []}
    kwargs = oauth.async_request.call_args
    assert kwargs.args[:2] == (
        "GET",
        f"https://api.bdrthermea.net/Mobile/api/appliances/{APPLIANCE_ID}"
        "/energyconsumption/daily",
    )
    assert kwargs.kwargs["params"] == {
        "startDate": "2026-01-09T00:00:00.000Z",
        "endDate": "2026-01-10T23:59:59.999Z",
    }
    assert "Ocp-Apim-Subscription-Key" in kwargs.kwargs["headers"]


async def test_action_returns_history(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Retrieve one day without writing entities or invoking heat controls."""
    await setup_integration(hass, config_entry, mock_api)
    appliance = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, APPLIANCE_ID), config_entry.entry_id
    )
    assert appliance is not None
    mock_api.async_get_consumption_data_for_range.return_value = {
        "data": [_january_9()]
    }

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ENERGY_HISTORY,
        {
            "device_id": appliance.id,
            "start_date": "2026-01-09",
            "end_date": "2026-01-09",
        },
        blocking=True,
        return_response=True,
    )
    assert result["appliance_id"] == APPLIANCE_ID
    assert result["days"][0]["heat_pump_heating_cop"] == round(68 / 18, 2)
    assert not result["missing_dates"]
    mock_api.async_get_consumption_data_for_range.assert_awaited_once_with(
        APPLIANCE_ID, date(2026, 1, 9), date(2026, 1, 9)
    )
    mock_api.async_set_manual.assert_not_awaited()


async def test_action_parent_resolution_and_monthly_batches(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """A producer device targets its appliance; dates are split into batches."""
    await setup_integration(hass, config_entry, mock_api)
    hp = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, f"{APPLIANCE_ID}_1"), config_entry.entry_id
    )
    assert hp is not None
    mock_api.async_get_consumption_data_for_range.return_value = {"data": []}

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ENERGY_HISTORY,
        {
            "device_id": hp.id,
            "start_date": "2026-01-01",
            "end_date": "2026-02-05",
        },
        blocking=True,
        return_response=True,
    )
    assert len(result["missing_dates"]) == 36
    assert mock_api.async_get_consumption_data_for_range.await_count == 2


async def test_action_rejects_wrong_device_and_dates(
    hass: HomeAssistant, config_entry, mock_api
) -> None:
    """Reject mistaken targets or excessive ranges before sending API calls."""
    await setup_integration(hass, config_entry, mock_api)
    service = SERVICE_GET_ENERGY_HISTORY
    with pytest.raises(HomeAssistantError, match="Select an appliance"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {
                "device_id": "not-a-remeha-device",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
            },
            blocking=True,
            return_response=True,
        )

    with pytest.raises(HomeAssistantError, match="at most 366"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {
                "device_id": "not-a-remeha-device",
                "start_date": "2024-01-01",
                "end_date": "2025-01-02",
            },
            blocking=True,
            return_response=True,
        )
    mock_api.async_get_consumption_data_for_range.assert_not_awaited()


def test_selected_period_cop_is_weighted_and_daily_cops_remain() -> None:
    """Period COP is total heat divided by total electricity, not mean daily COP."""
    first = _january_9()
    second = _january_9()
    second["timeStamp"] = "2026-01-10T00:00:00+00:00"
    first_pump = first["producerPerformanceStatistics"]["producers"][0]
    second_pump = second["producerPerformanceStatistics"]["producers"][0]
    first_pump["energyConsumptionCH"] = 1
    first_pump["energyProductionCH"] = 8
    second_pump["energyConsumptionCH"] = 9
    second_pump["energyProductionCH"] = 36

    result = combine_history(
        date(2026, 1, 9), date(2026, 1, 10), [{"data": [first, second]}]
    )

    assert [day["heat_pump_heating_cop"] for day in result["days"]] == [8.0, 4.0]
    assert result["period"]["complete"] is True
    assert result["period"]["days_requested"] == 2
    assert result["period"]["days_reported"] == 2
    assert result["period"]["heat_pump_heating_consumed_kwh"] == 10.0
    assert result["period"]["heat_pump_heating_delivered_kwh"] == 44.0
    assert result["period"]["heat_pump_heating_cop"] == 4.4
    assert "timestamp" not in result["days"][0]


def test_response_values_rounded_at_output_boundary() -> None:
    """Round COP and kWh for the action, without rounding input arithmetic."""
    item = _january_9()
    pump = item["producerPerformanceStatistics"]["producers"][0]
    pump["energyConsumptionCH"] = 1.2345
    pump["energyProductionCH"] = 5.6789
    result = combine_history(date(2026, 1, 9), date(2026, 1, 9), [{"data": [item]}])
    day = result["days"][0]
    assert day["heat_pump_heating_consumed_kwh"] == 1.23
    assert day["heat_pump_heating_delivered_kwh"] == 5.68
    assert day["heat_pump_heating_cop"] == round(5.6789 / 1.2345, 2)
    assert day["producers"][0]["heating_consumed_kwh"] == 1.23
    assert result["period"]["heat_pump_heating_consumed_kwh"] == 1.23
    assert result["period"]["heat_pump_heating_cop"] == round(5.6789 / 1.2345, 2)


def test_missing_gas_does_not_hide_valid_heat_pump_period_cop() -> None:
    """Gas and electricity validity remain independent on complete dates."""
    item = _january_9()
    item["producerPerformanceStatistics"]["producers"][1]["energyConsumptionCH"] = None
    result = combine_history(date(2026, 1, 9), date(2026, 1, 9), [{"data": [item]}])
    assert result["period"]["complete"] is True
    assert result["period"]["gas_heating_consumed_kwh"] is None
    assert result["period"]["heat_pump_heating_cop"] == round(68 / 18, 2)


def test_conflicting_day_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Conflict is flagged by date without leaking producer payloads to logs."""
    altered = _january_9()
    altered["producerPerformanceStatistics"]["producers"][0]["energyConsumptionCH"] = 12
    with caplog.at_level("WARNING"):
        result = combine_history(
            date(2026, 1, 9),
            date(2026, 1, 9),
            [{"data": [_january_9(), altered, _january_9()]}],
        )
    assert result["missing_dates"] == ["2026-01-09"]
    assert "2026-01-09" in caplog.text
    assert "Conflicting" in caplog.text


def test_unmodified_real_consumption_fixture_has_expected_shape() -> None:
    """Check the existing anonymized daily API fixture without synthesized rows."""
    raw = load_fixture("consumption.json")
    assert isinstance(raw["data"], list)
    assert isinstance(raw["data"][0]["producerPerformanceStatistics"]["producers"], list)
    row = normalize_history_day(raw["data"][0])
    assert row is not None
    assert row["heat_pump_heating_consumed_kwh"] == 4.0
    assert row["gas_heating_consumed_kwh"] == 1.0


def test_incomplete_period_totals_use_only_reported_days() -> None:
    """Available days are useful even when today or tomorrow is missing."""
    first = _january_9()
    second = _january_9()
    second["timeStamp"] = "2026-01-10T00:00:00+00:00"

    result = combine_history(
        date(2026, 1, 9), date(2026, 1, 11), [{"data": [first, second]}]
    )

    assert result["missing_dates"] == ["2026-01-11"]
    assert result["period"]["complete"] is False
    assert result["period"]["days_requested"] == 3
    assert result["period"]["days_reported"] == 2
    assert result["period"]["heat_pump_heating_consumed_kwh"] == 36.0
    assert result["period"]["heat_pump_heating_delivered_kwh"] == 136.0
    assert result["period"]["heat_pump_heating_cop"] == round(136 / 36, 2)
    assert result["period"]["gas_heating_consumed_kwh"] == 4.0
    assert [d["heat_pump_heating_cop"] for d in result["days"]] == [
        round(68 / 18, 2),
        round(68 / 18, 2),
    ]


def test_partial_period_does_not_treat_unknown_energy_as_zero() -> None:
    """An unknown reported-day input invalidates only the dependent totals."""
    first = _january_9()
    second = _january_9()
    second["timeStamp"] = "2026-01-10T00:00:00+00:00"
    second["producerPerformanceStatistics"]["producers"][0][
        "energyConsumptionCH"
    ] = None

    result = combine_history(
        date(2026, 1, 9), date(2026, 1, 11), [{"data": [first, second]}]
    )

    assert result["period"]["complete"] is False
    assert result["period"]["heat_pump_heating_consumed_kwh"] is None
    assert result["period"]["heat_pump_heating_delivered_kwh"] == 136.0
    assert result["period"]["heat_pump_heating_cop"] is None
    assert result["period"]["gas_heating_consumed_kwh"] == 4.0


def test_conflicting_day_keeps_totals_for_other_reported_days() -> None:
    """Conflicts omit a date, without suppressing clean partial-period totals."""
    second = _january_9()
    second["timeStamp"] = "2026-01-10T00:00:00+00:00"
    altered = copy.deepcopy(second)
    altered["producerPerformanceStatistics"]["producers"][0][
        "energyConsumptionCH"
    ] = 17.0

    result = combine_history(
        date(2026, 1, 9),
        date(2026, 1, 10),
        [{"data": [_january_9(), second, altered]}],
    )

    assert result["missing_dates"] == ["2026-01-10"]
    assert result["period"]["complete"] is False
    assert result["period"]["days_reported"] == 1
    assert result["period"]["heat_pump_heating_consumed_kwh"] == 18.0
    assert result["period"]["heat_pump_heating_cop"] == round(68 / 18, 2)


def test_period_without_any_reported_days_has_unknown_totals() -> None:
    """No data is not the same as zero energy."""
    result = combine_history(
        date(2026, 1, 9), date(2026, 1, 10), [{"data": []}]
    )

    assert result["period"]["complete"] is False
    assert result["period"]["days_requested"] == 2
    assert result["period"]["days_reported"] == 0
    assert result["period"]["heat_pump_heating_consumed_kwh"] is None
    assert result["period"]["heat_pump_heating_delivered_kwh"] is None
    assert result["period"]["heat_pump_heating_cop"] is None
    assert result["period"]["gas_heating_consumed_kwh"] is None


async def _history(hass: HomeAssistant, config_entry, start: str, end: str) -> dict:
    """Run the action for the appliance."""
    appliance = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, APPLIANCE_ID), config_entry.entry_id
    )
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_ENERGY_HISTORY,
        {"device_id": appliance.id, "start_date": start, "end_date": end},
        blocking=True,
        return_response=True,
    )


def _day(day: str) -> dict:
    """Return a reported day of the hybrid with the given date."""
    item = _january_9()
    item["timeStamp"] = f"{day}T00:00:00+00:00"
    return item


@pytest.mark.parametrize("end", ["2026-11-09", "2026-11-10"])
async def test_action_leaves_out_today(
    hass: HomeAssistant, config_entry, mock_api, freezer, end
) -> None:
    """Today isn't complete yet, so the period ends yesterday.

    The result is the same with today or a later day as the end date, also when
    the API returns today's figures.
    """
    freezer.move_to("2026-11-09 12:00:00+00:00")
    await setup_integration(hass, config_entry, mock_api)
    mock_api.async_get_consumption_data_for_range.return_value = {
        "data": [_day("2026-11-08"), _day("2026-11-09")]
    }

    result = await _history(hass, config_entry, "2026-11-08", end)

    mock_api.async_get_consumption_data_for_range.assert_awaited_once_with(
        APPLIANCE_ID, date(2026, 11, 8), date(2026, 11, 8)
    )
    assert result["end_date"] == "2026-11-08"
    assert [day["date"] for day in result["days"]] == ["2026-11-08"]
    assert result["period"]["days_requested"] == 1
    assert result["period"]["complete"] is True


@pytest.mark.parametrize("start", ["2026-11-09", "2026-11-10"])
async def test_action_rejects_period_from_today(
    hass: HomeAssistant, config_entry, mock_api, freezer, start
) -> None:
    """A period that starts today or later has no whole days."""
    freezer.move_to("2026-11-09 12:00:00+00:00")
    await setup_integration(hass, config_entry, mock_api)

    with pytest.raises(HomeAssistantError, match="before today"):
        await _history(hass, config_entry, start, "2026-11-10")

    mock_api.async_get_consumption_data_for_range.assert_not_awaited()
