#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "kernel_api/v1"
DEFAULT_STAGE_ORDER_PATH = "docs/projects/archive/OS-Stale-2026-02-28/contracts/stage-order-v1.json"


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _load_stage_order(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    stage_order = payload.get("stage_order")
    if not isinstance(stage_order, list) or not all(isinstance(item, str) and item for item in stage_order):
        raise ValueError("stage-order-v1.json must contain non-empty string list field 'stage_order'")
    return stage_order


def _stage_index(stage_order: list[str], stage_name: str) -> int:
    try:
        return stage_order.index(stage_name)
    except ValueError:
        return len(stage_order) + 999


def _normalized_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": issue.get("contract_version"),
        "level": issue.get("level"),
        "stage": issue.get("stage"),
        "code": issue.get("code"),
        "location": issue.get("location"),
        "details": issue.get("details") if isinstance(issue.get("details"), dict) else {},
    }


def _issue_key(stage_order: list[str], issue: dict[str, Any]) -> tuple[int, str, str, str]:
    normalized = _normalized_issue(issue)
    details_digest = _digest(normalized.get("details", {}))
    stage = str(normalized.get("stage") or "")
    return (
        _stage_index(stage_order, stage),
        str(normalized.get("location") or ""),
        str(normalized.get("code") or ""),
        details_digest,
    )


def _bucketized_issues(stage_order: list[str], issues: list[dict[str, Any]]) -> dict[tuple[int, str, str, str], list[str]]:
    buckets: dict[tuple[int, str, str, str], list[str]] = {}
    for issue in issues:
        key = _issue_key(stage_order, issue)
        norm = _normalized_issue(issue)
        entry_digest = _digest(norm)
        buckets.setdefault(key, []).append(entry_digest)
    for key in list(buckets.keys()):
        buckets[key] = sorted(buckets[key])
    return buckets


def _normalize_report_for_id(report: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(report)
    material["report_id"] = None
    mismatches = material.get("mismatches_detail")
    if isinstance(mismatches, list):
        for mismatch in mismatches:
            if isinstance(mismatch, dict):
                mismatch["diagnostic"] = None
    return material


def _mismatch_sort_key(mismatch: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(mismatch.get("turn_id", "")),
        int(mismatch.get("stage_index", 10_000)),
        int(mismatch.get("ordinal", 0)),
        str(mismatch.get("surface", "")),
        str(mismatch.get("path", "")),
    )


def _compare_turn(
    *,
    stage_order: list[str],
    turn_id: str,
    expected_turn: dict[str, Any],
    actual_turn: dict[str, Any],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []

    expected_issues = expected_turn.get("issues")
    actual_issues = actual_turn.get("issues")
    if not isinstance(expected_issues, list):
        expected_issues = []
    if not isinstance(actual_issues, list):
        actual_issues = []

    exp_buckets = _bucketized_issues(stage_order, expected_issues)
    act_buckets = _bucketized_issues(stage_order, actual_issues)
    all_keys = sorted(set(exp_buckets.keys()) | set(act_buckets.keys()))

    for ordinal, key in enumerate(all_keys):
        exp_list = exp_buckets.get(key, [])
        act_list = act_buckets.get(key, [])
        if exp_list == act_list:
            continue
        stage_idx, location, code, details_digest = key
        stage_name = stage_order[stage_idx] if 0 <= stage_idx < len(stage_order) else "replay"
        mismatches.append(
            {
                "turn_id": turn_id,
                "stage_name": stage_name,
                "stage_index": stage_idx,
                "ordinal": ordinal,
                "surface": "issue",
                "path": location or "/issues",
                "expected_digest": _digest({"bucket": exp_list, "details_digest": details_digest}),
                "actual_digest": _digest({"bucket": act_list, "details_digest": details_digest}),
                "diagnostic": {
                    "code": code,
                    "expected_count": len(exp_list),
                    "actual_count": len(act_list),
                },
            }
        )

    return mismatches


def compare_payload(
    *,
    payload: dict[str, Any],
    stage_order_path: str = DEFAULT_STAGE_ORDER_PATH,
) -> dict[str, Any]:
    stage_order = _load_stage_order(Path(stage_order_path))

    expected = payload.get("expected")
    actual = payload.get("actual")
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        raise ValueError("payload must contain object fields 'expected' and 'actual'")

    mismatches: list[dict[str, Any]] = []
    status = "MATCH"
    exit_code: str | None = None

    expected_registry = expected.get("registry_digest")
    actual_registry = actual.get("registry_digest")
    if expected_registry != actual_registry:
        status = "DIVERGENT"
        exit_code = "E_REGISTRY_DIGEST_MISMATCH"
        mismatches.append(
            {
                "turn_id": "registry",
                "stage_name": "replay",
                "stage_index": _stage_index(stage_order, "replay"),
                "ordinal": 0,
                "surface": "registry_digest",
                "path": "/registry_digest",
                "expected_digest": expected_registry,
                "actual_digest": actual_registry,
                "diagnostic": {"reason": "registry digest mismatch"},
            }
        )

    expected_digests = expected.get("digests")
    actual_digests = actual.get("digests")
    if isinstance(expected_digests, dict) and isinstance(actual_digests, dict) and expected_digests != actual_digests:
        if exit_code is None:
            status = "DIVERGENT"
            exit_code = "E_REPLAY_VERSION_MISMATCH"
        mismatches.append(
            {
                "turn_id": "version",
                "stage_name": "replay",
                "stage_index": _stage_index(stage_order, "replay"),
                "ordinal": 0,
                "surface": "schema",
                "path": "/digests",
                "expected_digest": _digest(expected_digests),
                "actual_digest": _digest(actual_digests),
                "diagnostic": {"reason": "digest version mismatch"},
            }
        )

    expected_turns = expected.get("turn_results")
    actual_turns = actual.get("turn_results")
    if isinstance(expected_turns, list) and isinstance(actual_turns, list):
        actual_map: dict[str, dict[str, Any]] = {}
        for item in actual_turns:
            if isinstance(item, dict) and isinstance(item.get("turn_id"), str):
                actual_map[item["turn_id"]] = item

        for item in expected_turns:
            if not isinstance(item, dict):
                continue
            turn_id = item.get("turn_id")
            if not isinstance(turn_id, str) or not turn_id:
                continue
            actual_item = actual_map.get(turn_id)
            if not isinstance(actual_item, dict):
                status = "DIVERGENT"
                exit_code = exit_code or "E_REPLAY_INPUT_MISSING"
                mismatches.append(
                    {
                        "turn_id": turn_id,
                        "stage_name": "replay",
                        "stage_index": _stage_index(stage_order, "replay"),
                        "ordinal": 0,
                        "surface": "input",
                        "path": f"/turn_results/{turn_id}",
                        "expected_digest": _digest(item),
                        "actual_digest": None,
                        "diagnostic": {"reason": "missing actual turn"},
                    }
                )
                continue
            mismatches.extend(
                _compare_turn(
                    stage_order=stage_order,
                    turn_id=turn_id,
                    expected_turn=item,
                    actual_turn=actual_item,
                )
            )

    if mismatches and status == "MATCH":
        status = "DIVERGENT"
        exit_code = "E_REPLAY_EQUIVALENCE_FAILED"

    sorted_mismatches = sorted(mismatches, key=_mismatch_sort_key)
    report = {
        "contract_version": CONTRACT_VERSION,
        "mode": "compare_runs",
        "outcome": "PASS" if status == "MATCH" else "FAIL",
        "status": status,
        "exit_code": exit_code,
        "report_id": None,
        "runs_compared": 2,
        "turns_compared": len(expected.get("turn_results", [])) if isinstance(expected.get("turn_results"), list) else 0,
        "issues": [],
        "events": [],
        "digests": {
            "registry_digest": expected_registry if expected_registry == actual_registry else None,
            "policy_digest": expected.get("digests", {}).get("policy_digest") if isinstance(expected.get("digests"), dict) else None,
            "runtime_digest": expected.get("digests", {}).get("runtime_digest") if isinstance(expected.get("digests"), dict) else None,
        },
        "mismatches_detail": sorted_mismatches,
        "parity": {
            "kind": "structural_parity",
            "matches": 1 if status == "MATCH" else 0,
            "mismatches": 0 if status == "MATCH" else len(sorted_mismatches),
            "expected": {"run_id": str(expected.get("run_id", "run-a")), "turn_digests": []},
            "actual": {"run_id": str(actual.get("run_id", "run-b")), "turn_digests": []},
        },
    }
    report["report_id"] = _digest(_normalize_report_for_id(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare replay payloads and emit deterministic ReplayReport JSON.")
    parser.add_argument("--in", dest="input_path", required=True, help="Path to comparator input JSON.")
    parser.add_argument("--out", dest="output_path", required=False, help="Optional path to write replay report JSON.")
    parser.add_argument(
        "--stage-order",
        dest="stage_order_path",
        default=DEFAULT_STAGE_ORDER_PATH,
        help="Path to stage-order contract JSON.",
    )
    args = parser.parse_args()

    payload = json.loads(Path(args.input_path).read_text(encoding="utf-8"))
    report = compare_payload(payload=payload, stage_order_path=args.stage_order_path)
    out = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output_path:
        Path(args.output_path).write_text(out, encoding="utf-8")
    else:
        print(out, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
