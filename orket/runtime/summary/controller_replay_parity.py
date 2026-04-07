from __future__ import annotations

from typing import Any

from orket.application.workflows.protocol_hashing import hash_canonical_json

_PARITY_KIND = "controller_replay_parity_v1"


def _normalize_controller_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    child_rows_raw = value.get("child_results")
    child_rows = child_rows_raw if isinstance(child_rows_raw, list) else []
    normalized_children: list[dict[str, Any]] = []
    for row in child_rows:
        if not isinstance(row, dict):
            continue
        normalized_children.append(
            {
                "target_workload": str(row.get("target_workload") or ""),
                "status": str(row.get("status") or ""),
                "requested_timeout": row.get("requested_timeout"),
                "enforced_timeout": row.get("enforced_timeout"),
                "normalized_error": row.get("normalized_error"),
                "summary": row.get("summary") if isinstance(row.get("summary"), dict) else {},
            }
        )

    requested_caps = value.get("requested_caps")
    enforced_caps = value.get("enforced_caps")
    return {
        "controller_contract_version": str(value.get("controller_contract_version") or ""),
        "controller_workload_id": str(value.get("controller_workload_id") or ""),
        "status": str(value.get("status") or ""),
        "error_code": value.get("error_code"),
        "requested_caps": dict(requested_caps) if isinstance(requested_caps, dict) else {},
        "enforced_caps": dict(enforced_caps) if isinstance(enforced_caps, dict) else {},
        "child_results": normalized_children,
    }


def _normalize_observability_projection(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(dict(row))
    return normalized


def _normalize_controller_output(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"controller_summary": {}, "controller_observability_projection": []}
    return {
        "controller_summary": _normalize_controller_summary(value.get("controller_summary")),
        "controller_observability_projection": _normalize_observability_projection(
            value.get("controller_observability_projection")
        ),
    }


def _collect_differences(
    *,
    expected: Any,
    actual: Any,
    path: str,
    differences: list[dict[str, Any]],
) -> None:
    if type(expected) is not type(actual):
        differences.append({"path": path, "expected": expected, "actual": actual})
        return

    if isinstance(expected, dict):
        keys = sorted(set(expected.keys()) | set(actual.keys()))
        for key in keys:
            child_path = f"{path}.{key}"
            if key not in expected:
                differences.append({"path": child_path, "expected": None, "actual": actual.get(key)})
                continue
            if key not in actual:
                differences.append({"path": child_path, "expected": expected.get(key), "actual": None})
                continue
            _collect_differences(
                expected=expected.get(key),
                actual=actual.get(key),
                path=child_path,
                differences=differences,
            )
        return

    if isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append({"path": f"{path}.length", "expected": len(expected), "actual": len(actual)})
        for index in range(min(len(expected), len(actual))):
            _collect_differences(
                expected=expected[index],
                actual=actual[index],
                path=f"{path}[{index}]",
                differences=differences,
            )
        return

    if expected != actual:
        differences.append({"path": path, "expected": expected, "actual": actual})


def compare_controller_replay_outputs(
    *, expected_output: dict[str, Any], actual_output: dict[str, Any]
) -> dict[str, Any]:
    expected_normalized = _normalize_controller_output(expected_output)
    actual_normalized = _normalize_controller_output(actual_output)
    differences: list[dict[str, Any]] = []
    _collect_differences(
        expected=expected_normalized,
        actual=actual_normalized,
        path="$",
        differences=differences,
    )
    expected_projection = expected_normalized.get("controller_observability_projection", [])
    actual_projection = actual_normalized.get("controller_observability_projection", [])
    return {
        "parity_kind": _PARITY_KIND,
        "parity_ok": len(differences) == 0,
        "difference_count": len(differences),
        "differences": differences,
        "expected_digest": hash_canonical_json(expected_normalized),
        "actual_digest": hash_canonical_json(actual_normalized),
        "expected_projection_digest": hash_canonical_json(expected_projection),
        "actual_projection_digest": hash_canonical_json(actual_projection),
        "expected": expected_normalized,
        "actual": actual_normalized,
    }


__all__ = ["compare_controller_replay_outputs"]
