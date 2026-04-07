import os
from datetime import UTC, datetime
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
_current_level_cache: tuple[str, int] | None = None


def get_current_level() -> int:
    global _current_level_cache
    raw = os.getenv("ORKET_LOG_LEVEL", "info").strip().lower()
    if _current_level_cache is not None and _current_level_cache[0] == raw:
        return _current_level_cache[1]
    level = CONSOLE_LEVELS.get(raw, CONSOLE_LEVELS["info"])
    _current_level_cache = (raw, level)
    return level


def reset_current_level_cache() -> None:
    global _current_level_cache
    _current_level_cache = None


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

    # Simple calculation based on your provided info:
    # Feb 6, 2026 is end of Q1 S6.
    # Base date: Feb 2, 2026 was start of Q1 S6.
    base_tz = date_obj.tzinfo or UTC
    base_date = datetime(2026, 2, 2, tzinfo=base_tz)
    base_q, base_s = 1, 6

    delta_weeks = (date_obj - base_date).days // 7
    total_sprints = base_s + delta_weeks

    q = base_q + (total_sprints - 1) // 13
    s = (total_sprints - 1) % 13 + 1

    return f"Q{q} S{s}"


def _ts() -> str:
    return now_local().isoformat()
