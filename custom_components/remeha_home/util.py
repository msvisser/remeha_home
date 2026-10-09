"""Helpers for the Remeha Home integration."""

from __future__ import annotations

from datetime import datetime

import homeassistant.util.dt as dt_util


def remeha_time(value: str | None) -> datetime | None:
    """Convert a Remeha API time to an aware datetime.

    The API sends local times with a 'Z' suffix (as the existing Next Setpoint
    Time sensor already assumes), and 0001-01-01T00:00:00Z for "not set".
    """
    if not value or str(value).startswith("0001-"):
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    return parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
