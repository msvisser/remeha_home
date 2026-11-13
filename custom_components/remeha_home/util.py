"""Utility helpers for the Remeha Home integration."""

from __future__ import annotations

from datetime import datetime

import homeassistant.util.dt as dt_util


def detect_dhw_setpoint_activity(
    target: float | None,
    comfort: float | None,
    reduced: float | None,
    tolerance: float = 0.25,
) -> str | None:
    """Return 'Comfort', 'Eco', or None based on which setpoint matches the target."""
    if (
        comfort is not None
        and target is not None
        and abs(target - comfort) < tolerance
    ):
        return "Comfort"

    if (
        reduced is not None
        and target is not None
        and abs(target - reduced) < tolerance
    ):
        return "Eco"

    return None


def supports_reduced_setpoint(hot_water_zone: dict) -> bool:
    """Return whether the eco (reduced) setpoint of a hot water zone can be changed.

    Remeha only accepts it for a zone with a tank. A combi boiler doesn't keep
    water warm in eco mode, so it has no eco temperature to set.
    """
    return hot_water_zone.get("dhwType", "Tank") == "Tank"


def reports_water_pressure(appliance: dict) -> bool:
    """Return whether an appliance reports its water pressure.

    Some boilers, such as a Brötje BOK19 with only an analog pressure gauge, report
    no pressure (null) and waterPressureOK false, which would look like a problem.
    """
    return appliance.get("waterPressure") is not None


def reports_dhw_temperature(hot_water_zone: dict) -> bool:
    """Return whether a hot water zone reports its water temperature.

    A combi boiler has no hot water tank, and Remeha reports no temperature for it.
    """
    return not (
        hot_water_zone.get("dhwType") == "Combi"
        and hot_water_zone.get("dhwTemperature") is None
    )


def remeha_time(value: str | None) -> datetime | None:
    """Convert a Remeha API time to an aware datetime.

    The API sends local times with a 'Z' suffix, and a time in the year 1
    (0001-01-01T00:00:00Z) for "not set". The boost end time and the end of a
    temporary override are the exceptions, use remeha_utc_time() for those.
    """
    if not value or str(value).startswith("0001-"):
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    return parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)


def remeha_utc_time(value: str | None) -> datetime | None:
    """Convert a Remeha API time in UTC to an aware datetime.

    Unlike the other times of the API, the boost end time and the end of a
    temporary override are in UTC. Measured on a live system: a temporary
    override until the schedule resumes at 22:00 CEST ends at 20:00:00Z, and a
    30 minute boost started at 14:41:59 CEST ends at 13:11:59.2692621Z.
    """
    if not value or str(value).startswith("0001-"):
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt_util.UTC)
    return parsed
