from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def configured_timezone_name() -> str:
    return (os.getenv("ORKET_TIMEZONE") or "UTC").strip()


def configured_timezone() -> tzinfo:
    name = configured_timezone_name()
    upper = name.upper()

    # Explicit MST handling for teams that want fixed Mountain Standard Time all year.
    if upper == "MST":
        return timezone(timedelta(hours=-7), name="MST")

    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def now_local() -> datetime:
    return datetime.now(configured_timezone())
