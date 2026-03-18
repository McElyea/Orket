from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable


PROTOCOL_VERSION = "protocol-governed/v5.1"
VALIDATOR_VERSION = "turn-validator/v1"


class ProtocolCanonicalizationError(ValueError):
    """Raised when a payload cannot be represented as canonical protocol JSON."""


def _ensure_json_compatible(value: Any, *, path: str = "value") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolCanonicalizationError(f"Non-finite numeric value at {path}")
        return value
    if isinstance(value, list):
        return [_ensure_json_compatible(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, tuple):
        return [_ensure_json_compatible(item, path=f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ProtocolCanonicalizationError(f"Non-string object key at {path}: {type(key).__name__}")
            normalized[key] = _ensure_json_compatible(child, path=f"{path}.{key}")
        return normalized
    raise ProtocolCanonicalizationError(f"Unsupported canonical JSON value at {path}: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    normalized = _ensure_json_compatible(value)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_hex(payload: str | bytes) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(raw).hexdigest()


def hash_canonical_json(value: Any) -> str:
    return sha256_hex(canonical_json_bytes(value))


def hash_framed_fields(kind: str, fields: Iterable[Any], *, version: int = 1) -> str:
    return hash_canonical_json({"v": int(version), "kind": str(kind), "fields": list(fields)})


def build_step_id(*, issue_id: str, turn_index: int) -> str:
    return f"{str(issue_id).strip()}:{int(turn_index)}"


def derive_operation_id(*, run_id: str, step_id: str, tool_index: int) -> str:
    return hash_framed_fields(
        "operation_id",
        [str(run_id).strip(), str(step_id).strip(), int(tool_index)],
    )


def derive_step_seed(*, run_seed: str, run_id: str, step_id: str) -> str:
    return hash_framed_fields(
        "step_seed",
        [str(run_seed).strip(), str(run_id).strip(), str(step_id).strip()],
    )


def default_protocol_hash() -> str:
    return hash_framed_fields("protocol_hash", [PROTOCOL_VERSION])


def default_tool_schema_hash() -> str:
    schema_surface = {
        "envelope_keys": ["content", "tool_calls"],
        "tool_call_keys": ["tool", "args"],
        "args_type": "object",
    }
    return hash_framed_fields("tool_schema_hash", [schema_surface])


def hash_env_allowlist(env_allowlist: dict[str, Any] | None) -> str:
    payload = {}
    if isinstance(env_allowlist, dict):
        payload = {
            str(key): str(value)
            for key, value in sorted(env_allowlist.items(), key=lambda item: str(item[0]))
            if str(key).strip()
        }
    return hash_framed_fields("env_allowlist", [payload])


def hash_network_allowlist(destinations: list[str] | None) -> str:
    normalized = sorted({str(item).strip() for item in (destinations or []) if str(item).strip()})
    return hash_framed_fields("network_allowlist", [normalized])


def hash_clock_artifact_ref(value: str | None) -> str:
    normalized = str(value or "").strip()
    return hash_framed_fields("clock_artifact_ref", [normalized])
