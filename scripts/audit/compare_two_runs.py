#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.kernel.v1.canonical import first_diff_path
from scripts.audit.audit_support import (
    authored_output_paths,
    build_identity_replacements,
    collect_turn_records,
    contract_verdict_candidates,
    evaluate_run_completeness,
    load_json_object,
    load_run_summary_object,
    normalize_json_surface,
    normalize_text,
    now_utc_iso,
    read_json,
    replace_identity_tokens,
    resolve_workspace_relative_path,
    surface_digest,
    text_diff_location,
    write_report,
)

DEFAULT_OUTPUT = "benchmarks/results/audit/compare_two_runs.json"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_surface(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return read_json(path)
    return normalize_text(path.read_text(encoding="utf-8"))


def _surface_record(
    *,
    group: str,
    label: str,
    relative_path: str,
    left_path: Path,
    right_path: Path,
    left_replacements: list[tuple[str, str]],
    right_replacements: list[tuple[str, str]],
) -> dict[str, Any]:
    left_raw = _load_surface(left_path)
    right_raw = _load_surface(right_path)
    if isinstance(left_raw, (dict, list)) and isinstance(right_raw, (dict, list)):
        left_value = normalize_json_surface(left_raw, surface_kind=label, replacements=left_replacements)
        right_value = normalize_json_surface(right_raw, surface_kind=label, replacements=right_replacements)
        diff = {"path": first_diff_path(_json_bytes(left_value), _json_bytes(right_value))}
    else:
        left_value = replace_identity_tokens(str(left_raw), left_replacements)
        right_value = replace_identity_tokens(str(right_raw), right_replacements)
        diff = text_diff_location(str(left_value), str(right_value))
    return {
        "group": group,
        "label": label,
        "relative_path": relative_path,
        "left_raw_digest": surface_digest(left_raw),
        "right_raw_digest": surface_digest(right_raw),
        "left_digest": surface_digest(left_value),
        "right_digest": surface_digest(right_value),
        "raw_equal": left_raw == right_raw,
        "equal": left_value == right_value,
        "first_diff": diff,
    }


def _required_surface_records(
    *,
    workspace: Path,
    session_id: str,
    replacements: list[tuple[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    summary = load_run_summary_object(workspace / "runs" / str(session_id).strip() / "run_summary.json")
    rows.append(
        {
            "group": "run_summary",
            "label": "run_summary",
            "relative_path": "runs/<session_id>/run_summary.json",
            "path": workspace / "runs" / str(session_id).strip() / "run_summary.json",
        }
    )
    for relative_path in authored_output_paths(summary):
        try:
            path = resolve_workspace_relative_path(workspace, relative_path)
        except ValueError:
            missing.append(relative_path)
            continue
        rows.append(
            {
                "group": "authored_output",
                "label": "authored_output",
                "relative_path": str(replace_identity_tokens(relative_path, replacements)),
                "path": path,
            }
        )
    for candidate in contract_verdict_candidates(summary):
        relative_path = str(candidate["path"])
        try:
            path = resolve_workspace_relative_path(workspace, relative_path)
        except ValueError:
            missing.append(relative_path)
            continue
        rows.append(
            {
                "group": "contract_verdict",
                "label": str(candidate["name"]),
                "relative_path": str(replace_identity_tokens(relative_path, replacements)),
                "path": path,
            }
        )
    for turn in collect_turn_records(workspace, session_id):
        turn_dir = Path(turn["turn_dir"])
        turn_ref = f"turns/{int(turn['ordinal']):03d}_{int(turn['turn_index']):03d}_{turn['role']}"
        for name, label in (
            ("checkpoint.json", "checkpoint"),
            ("messages.json", "messages"),
            ("model_response.txt", "model_response"),
        ):
            rows.append(
                {
                    "group": "turn_capture",
                    "label": label,
                    "relative_path": f"{turn_ref}/{name}",
                    "path": turn_dir / name,
                }
            )
        parsed_tool_calls = turn_dir / "parsed_tool_calls.json"
        if parsed_tool_calls.exists():
            rows.append(
                {
                    "group": "turn_capture",
                    "label": "parsed_tool_calls",
                    "relative_path": f"{turn_ref}/parsed_tool_calls.json",
                    "path": parsed_tool_calls,
                }
            )
    for row in rows:
        if not Path(row["path"]).exists():
            missing.append(str(row["relative_path"]))
    return rows, missing


def build_report(
    *,
    workspace_a: Path,
    session_id_a: str,
    workspace_b: Path,
    session_id_b: str,
) -> dict[str, Any]:
    left_eval = evaluate_run_completeness(workspace=workspace_a, session_id=session_id_a)
    right_eval = evaluate_run_completeness(workspace=workspace_b, session_id=session_id_b)
    if not bool(left_eval["mar_complete"]) or not bool(right_eval["mar_complete"]):
        return {
            "schema_version": "audit.compare_two_runs.v1",
            "recorded_at_utc": now_utc_iso(),
            "proof_kind": "structural",
            "observed_path": "blocked",
            "observed_result": "environment blocker",
            "verdict": "blocked",
            "run_a": left_eval,
            "run_b": right_eval,
            "evidence_missing": {
                "run_a": list(left_eval["missing_evidence"]),
                "run_b": list(right_eval["missing_evidence"]),
            },
            "excluded_fresh_identity_differences": [],
            "first_in_scope_diff": None,
            "compared_surfaces": [],
        }

    left_turns = collect_turn_records(workspace_a, session_id_a)
    right_turns = collect_turn_records(workspace_b, session_id_b)
    left_summary = load_run_summary_object(Path(workspace_a) / "runs" / str(session_id_a).strip() / "run_summary.json")
    right_summary = load_run_summary_object(Path(workspace_b) / "runs" / str(session_id_b).strip() / "run_summary.json")
    left_replacements = build_identity_replacements(
        workspace=workspace_a,
        session_id=session_id_a,
        turn_records=left_turns,
        summary=left_summary,
    )
    right_replacements = build_identity_replacements(
        workspace=workspace_b,
        session_id=session_id_b,
        turn_records=right_turns,
        summary=right_summary,
    )

    left_rows, left_missing = _required_surface_records(
        workspace=workspace_a,
        session_id=session_id_a,
        replacements=left_replacements,
    )
    right_rows, right_missing = _required_surface_records(
        workspace=workspace_b,
        session_id=session_id_b,
        replacements=right_replacements,
    )
    if left_missing or right_missing or len(left_rows) != len(right_rows):
        return {
            "schema_version": "audit.compare_two_runs.v1",
            "recorded_at_utc": now_utc_iso(),
            "proof_kind": "structural",
            "observed_path": "blocked",
            "observed_result": "environment blocker",
            "verdict": "blocked",
            "run_a": left_eval,
            "run_b": right_eval,
            "evidence_missing": {
                "run_a": left_missing,
                "run_b": right_missing,
                "surface_count_mismatch": [len(left_rows), len(right_rows)],
            },
            "excluded_fresh_identity_differences": [],
            "first_in_scope_diff": None,
            "compared_surfaces": [],
        }

    compared_surfaces: list[dict[str, Any]] = []
    excluded_identity_diffs: list[dict[str, Any]] = []
    first_diff: dict[str, Any] | None = None
    verdict = "stable"
    for left_row, right_row in zip(left_rows, right_rows):
        record = _surface_record(
            group=str(left_row["group"]),
            label=str(left_row["label"]),
            relative_path=str(left_row["relative_path"]),
            left_path=Path(left_row["path"]),
            right_path=Path(right_row["path"]),
            left_replacements=left_replacements,
            right_replacements=right_replacements,
        )
        compared_surfaces.append(record)
        if (not record["raw_equal"]) and record["equal"]:
            excluded_identity_diffs.append(
                {
                    "group": record["group"],
                    "label": record["label"],
                    "relative_path": record["relative_path"],
                }
            )
        if first_diff is None and not bool(record["equal"]):
            first_diff = {
                "group": record["group"],
                "label": record["label"],
                "relative_path": record["relative_path"],
                "path": record["first_diff"]["path"],
                "line": record["first_diff"].get("line"),
                "column": record["first_diff"].get("column"),
                "left_digest": record["left_digest"],
                "right_digest": record["right_digest"],
            }
            verdict = "diverged"

    return {
        "schema_version": "audit.compare_two_runs.v1",
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary",
        "observed_result": "success" if verdict == "stable" else "failure",
        "verdict": verdict,
        "run_a": {
            "workspace": str(Path(workspace_a).resolve()),
            "session_id": str(session_id_a),
        },
        "run_b": {
            "workspace": str(Path(workspace_b).resolve()),
            "session_id": str(session_id_b),
        },
        "evidence_missing": {
            "run_a": [],
            "run_b": [],
        },
        "excluded_fresh_identity_differences": excluded_identity_diffs,
        "first_in_scope_diff": first_diff,
        "compared_surfaces": compared_surfaces,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two equivalent runs at the governed MAR surface.")
    parser.add_argument("--workspace-a", required=True, help="Workspace root for run A.")
    parser.add_argument("--session-id-a", required=True, help="Session id for run A.")
    parser.add_argument("--workspace-b", required=True, help="Workspace root for run B.")
    parser.add_argument("--session-id-b", required=True, help="Session id for run B.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Stable rerunnable JSON output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted JSON payload.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output_path = Path(str(args.output)).resolve()
    payload = build_report(
        workspace_a=Path(str(args.workspace_a)).resolve(),
        session_id_a=str(args.session_id_a),
        workspace_b=Path(str(args.workspace_b)).resolve(),
        session_id_b=str(args.session_id_b),
    )
    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"verdict={persisted.get('verdict')}",
                    f"first_diff={((persisted.get('first_in_scope_diff') or {}).get('path') if isinstance(persisted.get('first_in_scope_diff'), dict) else '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("verdict") or "") == "stable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
