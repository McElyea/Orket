from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def require_nervous_system_enabled() -> None:
    raw = str(os.environ.get("ORKET_ENABLE_NERVOUS_SYSTEM") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return
    raise ValueError("Nervous System v1 is disabled (set ORKET_ENABLE_NERVOUS_SYSTEM=true).")


def allow_pre_resolved_policy_flags() -> bool:
    raw = str(os.environ.get("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def use_tool_profile_resolver() -> bool:
    raw_value = os.environ.get("ORKET_USE_TOOL_PROFILE_RESOLVER")
    if raw_value is None:
        return True
    raw = str(raw_value).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def is_exfil_payload(payload: dict[str, Any]) -> bool:
    tool_profile = payload.get("tool_profile")
    if isinstance(tool_profile, dict) and bool(tool_profile.get("exfil")):
        return True
    target = payload.get("target")
    return bool(isinstance(target, str) and _is_non_local_target(target))


def _is_non_local_target(target: str) -> bool:
    text = str(target or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https", "ws", "wss", "ftp"}:
        return True
    if parsed.netloc:
        return True
    lower = text.lower()
    if lower.startswith("ssh://") or lower.startswith("tcp://") or lower.startswith("udp://"):
        return True
    if "://" in text:
        return True
    if "@" in text and ":" in text and "/" in text:
        return True
    if "\\" in text:
        return False
    if "/" in text or text.startswith("."):
        return False
    if "." in text and all(ch not in text for ch in ("/", "\\")):
        return True
    try:
        _ = Path(text)
    except (TypeError, ValueError, OSError):
        return True
    return False


__all__ = [
    "allow_pre_resolved_policy_flags",
    "is_exfil_payload",
    "require_nervous_system_enabled",
    "use_tool_profile_resolver",
]
