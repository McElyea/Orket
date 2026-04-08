import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from orket.naming import sanitize_name
from orket.time_utils import now_local

LOG_DIR = "logs"
CONSOLE_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
__all__ = [
    "CONSOLE_LEVELS",
    "ensure_log_dir",
    "get_eos_sprint",
    "get_current_level",
    "get_reload_excludes",
    "reset_current_level_cache",
    "sanitize_name",
]


@lru_cache(maxsize=8)
def _resolve_console_level(raw: str) -> int:
    return CONSOLE_LEVELS.get(raw, CONSOLE_LEVELS["info"])


def get_current_level() -> int:
    raw = os.getenv("ORKET_LOG_LEVEL", "info").strip().lower()
    return _resolve_console_level(raw)


def reset_current_level_cache() -> None:
    _resolve_console_level.cache_clear()


@lru_cache(maxsize=1)
def _eos_sprint_base_settings() -> tuple[str, int, int]:
    base_date = str(os.getenv("ORKET_EOS_SPRINT_BASE_DATE", "2026-02-02")).strip() or "2026-02-02"
    try:
        base_q = max(1, int(str(os.getenv("ORKET_EOS_SPRINT_BASE_QUARTER", "1")).strip() or "1"))
    except ValueError:
        base_q = 1
    try:
        base_s = max(1, int(str(os.getenv("ORKET_EOS_SPRINT_BASE_SPRINT", "6")).strip() or "6"))
    except ValueError:
        base_s = 6
    return (base_date, base_q, base_s)


def ensure_log_dir() -> None:
    """Create the log directory if it does not exist. Call from application startup."""
    Path(LOG_DIR).mkdir(exist_ok=True)


def get_reload_excludes() -> list[str]:
    """
    Returns a list of glob patterns to exclude from auto-reloading.
    Can be overridden via ORKET_RELOAD_EXCLUDES ("pattern1,pattern2").
    """
    env_val = os.getenv("ORKET_RELOAD_EXCLUDES")
    if env_val:
        return [p.strip() for p in env_val.split(",") if p.strip()]

    return ["workspace/*", "product/*", "logs/*", "*.db", ".git/*", "__pycache__/*"]


def get_eos_sprint(date_obj: datetime | None = None) -> str:
    """Calculates EOS Sprint based on 1-week sprints (Mon-Fri) and 13-sprint quarters."""
    if date_obj is None:
        date_obj = now_local()

    base_tz = date_obj.tzinfo or UTC
    base_date_raw, base_q, base_s = _eos_sprint_base_settings()
    try:
        parsed_base = datetime.fromisoformat(base_date_raw)
        if parsed_base.tzinfo is None:
            base_date = datetime(parsed_base.year, parsed_base.month, parsed_base.day, tzinfo=base_tz)
        else:
            base_date = parsed_base.astimezone(base_tz)
    except ValueError:
        base_date = datetime(2026, 2, 2, tzinfo=base_tz)
        base_q, base_s = 1, 6

    delta_weeks = (date_obj - base_date).days // 7
    total_sprints = base_s + delta_weeks

    q = base_q + (total_sprints - 1) // 13
    s = (total_sprints - 1) % 13 + 1

    return f"Q{q} S{s}"


def _ts() -> str:
    return now_local().isoformat()
