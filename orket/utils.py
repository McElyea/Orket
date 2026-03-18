import os
from datetime import UTC, datetime

from orket.naming import sanitize_name
from orket.time_utils import now_local

LOG_DIR = "logs"
CONSOLE_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
__all__ = [
    "CONSOLE_LEVELS",
    "CURRENT_LEVEL",
    "ensure_log_dir",
    "get_eos_sprint",
    "get_reload_excludes",
    "sanitize_name",
]


def _resolve_log_level() -> int:
    raw = os.getenv("ORKET_LOG_LEVEL", "info").strip().lower()
    return CONSOLE_LEVELS.get(raw, CONSOLE_LEVELS["info"])


def ensure_log_dir() -> None:
    """Create the log directory if it does not exist. Call from application startup."""
    os.makedirs(LOG_DIR, exist_ok=True)


CURRENT_LEVEL = _resolve_log_level()


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


def _ts():
    return now_local().isoformat()
