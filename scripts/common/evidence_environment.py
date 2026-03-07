from __future__ import annotations

import os
import platform
import sys
from datetime import UTC, datetime
from typing import Any, Iterable


DEFAULT_EVIDENCE_ENV_KEYS = (
    "ORKET_HOST",
    "ORKET_PORT",
    "ORKET_API_KEY",
    "ORKET_ALLOW_INSECURE_NO_API_KEY",
    "ORKET_LLM_PROVIDER",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def redact_env_value(key: str, value: str) -> str:
    key_upper = str(key or "").upper()
    if any(token in key_upper for token in ("KEY", "TOKEN", "PASSWORD", "SECRET")):
        return "<redacted>"
    if len(value) > 256:
        return value[:253] + "..."
    return value


def collect_environment_metadata(
    *,
    schema_version: str,
    package_mode: str,
    env_keys: Iterable[str],
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    toggles: dict[str, dict[str, Any]] = {}
    for key in sorted({str(item).strip() for item in env_keys if str(item).strip()}):
        raw = str(os.environ.get(key, ""))
        toggles[key] = {
            "set": bool(raw),
            "value": redact_env_value(key, raw) if raw else "",
        }

    payload: dict[str, Any] = {
        "schema_version": str(schema_version).strip(),
        "recorded_at_utc": utc_now_iso(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "python_executable": sys.executable,
        },
        "package_mode": str(package_mode or "").strip(),
        "env_toggles": toggles,
    }
    if extra_fields:
        payload.update(extra_fields)
    return payload
