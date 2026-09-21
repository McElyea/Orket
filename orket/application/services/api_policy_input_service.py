"""Capture API strategy values and admit recommendations against observed effects."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from orket_extension_sdk import FrozenJson


@dataclass(frozen=True)
class ApiArchiveInputs:
    card_ids: tuple[str, ...] | None
    build_id: str | None
    related_tokens: tuple[str, ...] | None
    archived_by: str
    reason: str | None


def capture_archive_inputs(request: Any) -> ApiArchiveInputs:
    return ApiArchiveInputs(card_ids=None if request.card_ids is None else tuple(request.card_ids),
        build_id=request.build_id, related_tokens=None if request.related_tokens is None else tuple(request.related_tokens),
        archived_by=request.archived_by or "api", reason=request.reason)


def admit_api_bool(value: Any) -> bool:
    if type(value) is not bool:
        raise ValueError("E_API_POLICY_INVALID_BOOLEAN")
    return value


def capture_json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or any(type(key) is not str for key in value):
        raise ValueError("E_API_POLICY_INVALID_OBJECT")
    return FrozenJson.freeze(value).thaw()


def capture_api_invocation(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("kwargs"), dict) and any(type(k) is not str for k in value["kwargs"]):
        raise ValueError("E_API_POLICY_INVALID_INVOCATION")
    payload = capture_json_object(value)
    if (set(payload) - {"method_name", "args", "kwargs", "unsupported_detail"}
            or type(payload.get("method_name")) is not str
            or type(payload.get("args", [])) is not list
            or type(payload.get("kwargs", {})) is not dict
            or ("unsupported_detail" in payload and type(payload["unsupported_detail"]) is not str)):
        raise ValueError("E_API_POLICY_INVALID_INVOCATION")
    return payload


def capture_preview_target(value: Any):
    payload = capture_json_object(value)
    if not {"mode", "asset_name", "department"} <= payload.keys() or any(type(v) is not str for v in payload.values()):
        raise ValueError("E_API_POLICY_INVALID_PREVIEW_TARGET")
    return MappingProxyType(payload)


def normalize_api_metrics(node: Any, observed: dict[str, Any]) -> dict[str, Any]:
    return capture_json_object(node.normalize_metrics(FrozenJson.freeze(observed)))


def order_explorer_items(node: Any, observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captured = tuple(MappingProxyType(dict(item)) for item in observed)
    proposal = node.sort_explorer_items(captured)
    if not isinstance(proposal, (list, tuple)):
        raise ValueError("E_API_POLICY_INVALID_EXPLORER_ITEMS")
    rows = [dict(row) for row in proposal]
    if any(set(row) != {"name", "is_dir", "ext"} or type(row["name"]) is not str
           or type(row["is_dir"]) is not bool or type(row["ext"]) is not str for row in rows):
        raise ValueError("E_API_POLICY_INVALID_EXPLORER_ITEMS")
    if len(rows) != len(observed) or sorted(rows, key=lambda row: row["name"]) != sorted(observed, key=lambda row: row["name"]):
        raise ValueError("E_API_POLICY_EXPLORER_FACT_CONTRADICTION")
    return rows


def normalize_archive_result(node: Any, archived_ids: list[str], missing_ids: list[str], archived_count: int):
    archived, missing = tuple(archived_ids), tuple(missing_ids)
    payload = capture_json_object(node.normalize_archive_response(
        archived_ids=archived, missing_ids=missing, archived_count=archived_count))
    expected_count = archived_count + len(set(archived))
    expected_sets = {"archived_ids": sorted(set(archived)), "missing_ids": sorted(set(missing))}
    valid = payload.get("ok") is True and type(payload.get("archived_count")) is int
    valid = valid and payload["archived_count"] == expected_count
    for key, expected in expected_sets.items():
        values = payload.get(key)
        valid = valid and type(values) is list and all(type(item) is str for item in values) and sorted(values) == expected
    if not valid:
        raise ValueError("E_API_ARCHIVE_RESULT_CONTRADICTION")
    return payload


def recommend_websocket_removal(node: Any, error: Exception) -> bool:
    category = "runtime_error" if isinstance(error, RuntimeError) else "value_error" if isinstance(error, ValueError) else "other"
    return admit_api_bool(node.should_remove_websocket(category))
