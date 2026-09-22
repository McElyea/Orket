import os
from collections.abc import Iterable
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from orket.core.contracts.eos_calendar import EosSprintBaseline
from orket.naming import sanitize_name
from orket.time_utils import now_local

LOG_DIR = "logs"
CONSOLE_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
__all__ = [
    "CONSOLE_LEVELS",
    "dedupe_ordered",
    "ensure_log_dir",
    "get_eos_sprint",
    "get_current_level",
    "get_reload_excludes",
    "reset_current_level_cache",
    "sanitize_name",
]


side_effecting = True


def dedupe_ordered(values: Iterable[Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


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
    baseline = EosSprintBaseline.from_environment(os.environ)
    return baseline.date, baseline.quarter, baseline.sprint


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
    """Legacy ambient-input adapter; pure calculation lives in EosSprintBaseline."""
    return EosSprintBaseline(*_eos_sprint_base_settings()).current_sprint(date_obj or now_local())


def _ts() -> str:
    return now_local().isoformat()
