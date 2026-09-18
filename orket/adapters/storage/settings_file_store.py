"""Synchronous settings file effects, invoked only inside an owned worker."""
from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from math import isfinite
from pathlib import Path
from typing import Any

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.verified_file import write_verified_bytes
from orket.core.contracts.protocol_hashing import canonical_json

side_effecting = True


def read_settings_document(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    payload = json.loads(raw, parse_constant=_invalid_constant, parse_float=_finite_float, object_pairs_hook=_unique_object)
    if not isinstance(payload, dict):
        raise ValueError("E_SETTINGS_OBJECT_REQUIRED")
    return payload


def _invalid_constant(value: str):
    raise ValueError("E_SETTINGS_NONFINITE_NUMBER")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise ValueError("E_SETTINGS_NONFINITE_NUMBER")
    return parsed


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("E_SETTINGS_DUPLICATE_KEY")
        result[key] = value
    return result


def write_settings_document(path: Path, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, indent=4, allow_nan=False).encode("utf-8")
    write_verified_bytes(path, raw, error_code="E_SETTINGS_WRITE_UNVERIFIED")


@contextmanager
def hold_settings_files(paths: tuple[Path, ...]):
    """Nonblocking native admission shared by all cooperating settings writers."""
    with ExitStack() as stack:
        for path in sorted(set(paths), key=str):
            locks = NativeFileLocks(path, suffix=".settings-locks", error_prefix="E_SETTINGS",
                                    empty_key_error="E_SETTINGS_LOCK_KEY")
            stack.enter_context(locks.hold_sync("settings-file"))
        yield


def retire_legacy_settings(path: Path, expected: dict[str, Any]) -> None:
    if canonical_json(read_settings_document(path)) != canonical_json(expected):
        raise ValueError("E_SETTINGS_LEGACY_CHANGED")
    path.unlink()
