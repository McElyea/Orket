from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

import aiofiles
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from orket_extension_sdk.controller import ControllerRunSummary, canonical_json

_CONTROLLER_RUN_FIELDS = (
    "event",
    "run_id",
    "controller_workload",
    "execution_depth",
    "declared_fanout",
    "accepted_fanout",
    "requested_caps",
    "enforced_caps",
    "result",
    "error_code",
)
_CONTROLLER_CHILD_FIELDS = (
    "event",
    "run_id",
    "child_index",
    "execution_order",
    "child_workload",
    "status",
    "requested_timeout",
    "enforced_timeout",
    "error_code",
)
_CAPS_FIELDS = ("max_depth", "max_fanout", "child_timeout_seconds")
_SCHEMA_CACHE: dict[str, Any] | None = None


class ObservabilityBatchSink(Protocol):
    async def emit_batch(self, *, run_id: str, events: list[dict[str, Any]]) -> None: ...


def emit_controller_run(
    *,
    run_id: str,
    controller_workload: str,
    execution_depth: int,
    declared_fanout: int | None,
    accepted_fanout: int,
    requested_caps: Mapping[str, Any],
    enforced_caps: Mapping[str, Any],
    result: str,
    error_code: str | None,
) -> dict[str, Any]:
    event = {
        "event": "controller_run",
        "run_id": run_id,
        "controller_workload": controller_workload,
        "execution_depth": execution_depth,
        "declared_fanout": declared_fanout,
        "accepted_fanout": accepted_fanout,
        "requested_caps": _canonicalize_caps(requested_caps),
        "enforced_caps": _canonicalize_caps(enforced_caps),
        "result": result,
        "error_code": error_code,
    }
    return canonicalize_event(event)


def emit_controller_child(
    *,
    run_id: str,
    child_index: int,
    child_workload: str,
    status: str,
    requested_timeout: int | None,
    enforced_timeout: int | None,
    error_code: str | None,
) -> dict[str, Any]:
    event = {
        "event": "controller_child",
        "run_id": run_id,
        "child_index": child_index,
        "execution_order": child_index,
        "child_workload": child_workload,
        "status": status,
        "requested_timeout": requested_timeout,
        "enforced_timeout": enforced_timeout,
        "error_code": error_code,
    }
    return canonicalize_event(event)


def canonicalize_event(event: Mapping[str, Any]) -> dict[str, Any]:
    event_name = str(event.get("event") or "").strip()
    if event_name == "controller_run":
        return _canonicalize_with_field_order(event, _CONTROLLER_RUN_FIELDS)
    if event_name == "controller_child":
        return _canonicalize_with_field_order(event, _CONTROLLER_CHILD_FIELDS)
    raise ValueError("controller.observability_event_invalid")


async def validate_observability_schema(
    events: Sequence[Mapping[str, Any]],
    *,
    schema_path: Path | None = None,
) -> None:
    schema = await _load_schema(schema_path=schema_path)
    validator = Draft202012Validator(schema)
    for index, event in enumerate(events):
        try:
            validator.validate(dict(event))
        except JsonSchemaValidationError as exc:
            raise ValueError(f"controller.observability_schema_invalid:index={index}") from exc


def canonical_projection(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for event in events:
        if "run_id" not in event:
            raise ValueError("controller.observability_event_invalid")
        event_without_run_id = {key: value for key, value in event.items() if key != "run_id"}
        projected.append(json.loads(canonical_json(event_without_run_id)))
    return projected


async def emit_observability_batch(
    *,
    run_id: str,
    envelope_payload: Mapping[str, Any],
    summary: ControllerRunSummary,
    sink: ObservabilityBatchSink | None = None,
    schema_path: Path | None = None,
) -> list[dict[str, Any]]:
    run_identifier = str(run_id or "").strip() or f"controller-{summary.summary_digest_sha256()[:16]}"
    accepted_fanout = len(summary.child_results)
    run_event = emit_controller_run(
        run_id=run_identifier,
        controller_workload=summary.controller_workload_id,
        execution_depth=_execution_depth_from_payload(envelope_payload),
        declared_fanout=_declared_fanout_from_payload(envelope_payload),
        accepted_fanout=accepted_fanout,
        requested_caps=_caps_payload(summary.requested_caps),
        enforced_caps=_caps_payload(summary.enforced_caps),
        result=summary.status,
        error_code=summary.error_code,
    )
    child_events = [
        emit_controller_child(
            run_id=run_identifier,
            child_index=index,
            child_workload=child.target_workload,
            status=_child_observability_status(child.status),
            requested_timeout=child.requested_timeout,
            enforced_timeout=child.enforced_timeout,
            error_code=child.normalized_error,
        )
        for index, child in enumerate(summary.child_results)
    ]
    events = [run_event, *child_events]
    canonical_events = [canonicalize_event(event) for event in events]
    await validate_observability_schema(canonical_events, schema_path=schema_path)
    if sink is not None:
        await sink.emit_batch(run_id=run_identifier, events=canonical_events)
    return canonical_events


def _canonicalize_with_field_order(event: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    event_keys = set(event.keys())
    expected = set(fields)
    if event_keys != expected:
        raise ValueError("controller.observability_event_invalid")
    return {key: event[key] for key in fields}


def _caps_payload(caps: Any) -> dict[str, Any]:
    if caps is None:
        return {}
    if hasattr(caps, "model_dump"):
        dumped = caps.model_dump(exclude_none=True)
    elif isinstance(caps, Mapping):
        dumped = dict(caps)
    else:
        raise ValueError("controller.observability_event_invalid")
    return _canonicalize_caps(dumped)


def _canonicalize_caps(caps: Mapping[str, Any]) -> dict[str, Any]:
    unknown = [key for key in caps.keys() if key not in _CAPS_FIELDS]
    if unknown:
        raise ValueError("controller.observability_event_invalid")
    return {key: caps[key] for key in _CAPS_FIELDS if key in caps}


def _execution_depth_from_payload(payload: Mapping[str, Any]) -> int:
    depth = payload.get("parent_depth")
    if isinstance(depth, int) and depth >= 0:
        return depth
    return 0


def _declared_fanout_from_payload(payload: Mapping[str, Any]) -> int | None:
    children = payload.get("children")
    if isinstance(children, list):
        return len(children)
    return None


def _child_observability_status(child_status: str) -> str:
    if child_status == "success":
        return "success"
    if child_status == "failed":
        return "failure"
    if child_status == "not_attempted":
        return "not_attempted"
    raise ValueError("controller.observability_event_invalid")


async def _load_schema(*, schema_path: Path | None = None) -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        target_path = (
            schema_path or Path(__file__).resolve().parents[2] / "schemas" / "controller_observability_v1.json"
        )
        async with aiofiles.open(target_path, "r", encoding="utf-8") as handle:
            _SCHEMA_CACHE = json.loads(await handle.read())
    return _SCHEMA_CACHE


__all__ = [
    "ObservabilityBatchSink",
    "canonical_projection",
    "canonicalize_event",
    "emit_controller_child",
    "emit_controller_run",
    "emit_observability_batch",
    "validate_observability_schema",
]
