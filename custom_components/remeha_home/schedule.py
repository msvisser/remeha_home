"""Turn the switching points of a clock program into a week schedule.

The API returns a clock program as a list of switching points, each with a day
(0 is Sunday, measured on a Remeha Elga Ace), a time, and for heating an activity
number or for hot water whether comfort is active. The schedule attribute of the
Clock program sensors has the same shape for heating and hot water: per day,
Monday first, a list of switching points with time, mode and setpoint.
"""

from __future__ import annotations

from typing import Any

# The API numbers the days from Sunday
DAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday")
# The order of the days in the schedule
SCHEDULE_DAYS = DAYS[1:] + DAYS[:1]


def _week(points: list[tuple[str, dict[str, Any]]]) -> dict[str, list[dict]]:
    """Group switching points per day, Monday first, each day sorted by time."""
    week: dict[str, list[dict]] = {day: [] for day in SCHEDULE_DAYS}
    for day, point in points:
        week[day].append(point)
    for day_points in week.values():
        day_points.sort(key=lambda point: point["time"])
    return week


def _switching_points(time_program: dict | None):
    """Yield the day name and the switching point, skipping invalid ones."""
    if not isinstance(time_program, dict):
        return
    for point in time_program.get("switchPoints") or []:
        if not isinstance(point, dict):
            continue
        day = point.get("day")
        time = point.get("time")
        if not isinstance(day, int) or not 0 <= day < len(DAYS):
            continue
        if not isinstance(time, str):
            continue
        yield DAYS[day], point


def heating_schedule(
    time_program: dict | None, activities: list[dict] | None
) -> dict[str, list[dict]] | None:
    """Return the week schedule of a heating clock program.

    The mode is the name of the activity, the setpoint its temperature. A switching
    point with its own temperature (customValue) uses that one.
    """
    if not isinstance(time_program, dict):
        return None
    heating = {
        activity.get("activityNumber"): activity
        for activity in activities or []
        if isinstance(activity, dict) and activity.get("type") == "Heating"
    }
    points = []
    for day, point in _switching_points(time_program):
        activity = heating.get(point.get("activity"), {})
        setpoint = point.get("customValue")
        if setpoint is None:
            setpoint = activity.get("temperature")
        points.append(
            (
                day,
                {
                    "time": point["time"],
                    "mode": activity.get("name"),
                    "setpoint": setpoint,
                },
            )
        )
    return _week(points)


def hot_water_schedule(
    time_program: dict | None, hot_water_zone: dict
) -> dict[str, list[dict]] | None:
    """Return the week schedule of a hot water clock program.

    The mode is Comfort or Eco, as in the Mode sensor, with the matching setpoint.
    A combi boiler doesn't keep water warm in Eco, so it has no Eco setpoint.
    """
    if not isinstance(time_program, dict):
        return None
    tank = hot_water_zone.get("dhwType") != "Combi"
    points = []
    for day, point in _switching_points(time_program):
        comfort = point.get("comfortActive") is True
        if comfort:
            setpoint = hot_water_zone.get("comfortSetPoint")
        else:
            setpoint = hot_water_zone.get("reducedSetpoint") if tank else None
        points.append(
            (
                day,
                {
                    "time": point["time"],
                    "mode": "Comfort" if comfort else "Eco",
                    "setpoint": setpoint,
                },
            )
        )
    return _week(points)
