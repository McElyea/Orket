from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.kernel.v1.canonical import odr_canonicalize
from scripts.common.run_summary_support import load_validated_run_summary_or_empty
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

REQUIRED_TURN_FILES = ("messages.json", "model_response.txt", "checkpoint.json")
ODR_VERDICT_FIELDS = ("history_rounds", "odr_stop_reason", "odr_valid", "odr_pending_decisions")
COMMON_VOLATILE_KEYS = {
    "captured_at",
    "duration_ms",
    "issue_id",
    "latency_ms",
    "operation_id",
    "produced_at",
    "recorded_at",
    "run_id",
    "source_hash",
    "step_id",
    "timestamp",
}
SURFACE_VOLATILE_KEYS = {
    "checkpoint": {"prompt_hash"},
    "runtime_verification": {"command_display"},
}


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = read_json(path)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_run_summary_object(path: Path) -> dict[str, Any]:
    return load_validated_run_summary_or_empty(path)


def normalize_text(value: str) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_workspace_relative_path(workspace: Path, relative_path: str) -> Path:
    token = str(relative_path or "").strip().replace("\\", "/")
    if not token:
        raise ValueError("workspace_relative_path_required")
    if Path(token).is_absolute():
        raise ValueError("absolute_paths_not_allowed")
    workspace_root = workspace.resolve()
    candidate = (workspace_root / token).resolve()
    if not candidate.is_relative_to(workspace_root):
        raise ValueError("workspace_relative_path_escape")
    return candidate


def collect_turn_records(workspace: Path, session_id: str) -> list[dict[str, Any]]:
    session_root = workspace / "observability" / str(session_id).strip()
    if not session_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    ordinal = 0
    for issue_dir in sorted(session_root.iterdir(), key=lambda item: item.name):
        if not issue_dir.is_dir():
            continue
        for turn_dir in sorted(issue_dir.iterdir(), key=lambda item: item.name):
            if not turn_dir.is_dir():
                continue
            prefix, _, suffix = turn_dir.name.partition("_")
            try:
                turn_index = int(prefix)
            except ValueError:
                turn_index = 0
            rows.append(
                {
                    "ordinal": ordinal,
                    "issue_id": issue_dir.name,
                    "turn_dir": turn_dir,
                    "turn_name": turn_dir.name,
                    "turn_index": turn_index,
                    "role": suffix,
                }
            )
            ordinal += 1
    return rows


def parsed_tool_calls_required(turn_dir: Path, checkpoint: dict[str, Any]) -> bool:
    tool_calls = checkpoint.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        return True
    if (turn_dir / "tool_parser_diagnostics.json").exists():
        return True
    return any(path.name.startswith("tool_result_") for path in turn_dir.glob("tool_result_*.json"))


def authored_output_paths(summary: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    artifact_contract = summary.get("artifact_contract")
    if isinstance(artifact_contract, dict):
        primary_output = str(artifact_contract.get("primary_output") or "").strip()
        if primary_output and primary_output not in seen:
            seen.add(primary_output)
            rows.append(primary_output)
    provenance = summary.get("truthful_runtime_artifact_provenance")
    if isinstance(provenance, dict):
        artifacts = provenance.get("artifacts")
        if isinstance(artifacts, list):
            for item in artifacts:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("artifact_path") or "").strip()
                if not path or path in seen:
                    continue
                seen.add(path)
                rows.append(path)
    odr_artifact_path = str(summary.get("odr_artifact_path") or "").strip()
    if odr_artifact_path and odr_artifact_path not in seen:
        seen.add(odr_artifact_path)
        rows.append(odr_artifact_path)
    return rows


def contract_verdict_candidates(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "name": "cards_runtime_verification",
            "path": "agent_output/verification/runtime_verification.json",
            "required_fields": (),
        }
    ]
    odr_artifact_path = str(summary.get("odr_artifact_path") or "").strip()
    if odr_artifact_path:
        rows.append(
            {
                "name": "odr_refinement",
                "path": odr_artifact_path,
                "required_fields": ODR_VERDICT_FIELDS,
            }
        )
    return rows


def evaluate_run_completeness(*, workspace: Path, session_id: str) -> dict[str, Any]:
    workspace_root = Path(workspace).resolve()
    run_summary_path = workspace_root / "runs" / str(session_id).strip() / "run_summary.json"
    summary = load_run_summary_object(run_summary_path)
    run_outcome_missing: list[str] = []
    if not run_summary_path.exists():
        run_outcome_missing.append("runs/<session_id>/run_summary.json")
    elif not summary:
        run_outcome_missing.append("run_summary.invalid_or_untrusted")
    required_run_fields = ("run_id", "status", "artifact_ids", "failure_reason")
    for key in required_run_fields:
        if key not in summary:
            run_outcome_missing.append(f"run_summary.{key}")
    cards_run = "execution_profile" in summary or "cards_runtime" in summary
    if cards_run:
        for key in ("stop_reason", "execution_profile"):
            if key not in summary:
                run_outcome_missing.append(f"run_summary.{key}")
    if bool(summary.get("odr_active")):
        for key in ("odr_active", "odr_artifact_path", "odr_stop_reason", "odr_valid", "odr_pending_decisions"):
            if key not in summary:
                run_outcome_missing.append(f"run_summary.{key}")
    run_outcome_present = not run_outcome_missing

    session_root = workspace_root / "observability" / str(session_id).strip()
    turn_records = collect_turn_records(workspace_root, session_id)
    turn_capture_missing: list[str] = []
    if not session_root.exists():
        turn_capture_missing.append("observability/<session_id>/")
    turn_rows: list[dict[str, Any]] = []
    for row in turn_records:
        turn_dir = Path(row["turn_dir"])
        checkpoint = load_json_object(turn_dir / "checkpoint.json")
        turn_missing = [name for name in REQUIRED_TURN_FILES if not (turn_dir / name).exists()]
        if parsed_tool_calls_required(turn_dir, checkpoint) and not (turn_dir / "parsed_tool_calls.json").exists():
            turn_missing.append("parsed_tool_calls.json")
        if turn_missing:
            for name in turn_missing:
                turn_capture_missing.append(f"{turn_dir.relative_to(workspace_root).as_posix()}/{name}")
        turn_rows.append(
            {
                "ordinal": int(row["ordinal"]),
                "issue_id": str(row["issue_id"]),
                "turn_name": str(row["turn_name"]),
                "turn_index": int(row["turn_index"]),
                "role": str(row["role"]),
                "missing_artifacts": turn_missing,
            }
        )
    turn_capture_present = session_root.exists() and not turn_capture_missing

    required_authored_outputs = authored_output_paths(summary)
    authored_output_missing: list[str] = []
    if not required_authored_outputs:
        authored_output_missing.append("no_authoritative_authored_outputs_named")
    for relative_path in required_authored_outputs:
        try:
            candidate = resolve_workspace_relative_path(workspace_root, relative_path)
        except ValueError:
            authored_output_missing.append(relative_path)
            continue
        if not candidate.exists():
            authored_output_missing.append(relative_path)
    authored_output_present = not authored_output_missing

    verdict_rows: list[dict[str, Any]] = []
    verdict_missing_candidates: list[str] = []
    verdict_present = False
    for candidate in contract_verdict_candidates(summary):
        relative_path = str(candidate["path"])
        required_fields = tuple(candidate["required_fields"])
        try:
            resolved_path = resolve_workspace_relative_path(workspace_root, relative_path)
        except ValueError:
            verdict_missing_candidates.append(relative_path)
            continue
        payload = load_json_object(resolved_path)
        missing_fields = [field for field in required_fields if field not in payload]
        exists = resolved_path.exists()
        valid = exists and (not required_fields or not missing_fields) and bool(payload)
        verdict_rows.append(
            {
                "name": str(candidate["name"]),
                "path": relative_path,
                "exists": exists,
                "missing_fields": missing_fields,
            }
        )
        if valid:
            verdict_present = True
        else:
            verdict_missing_candidates.append(
                relative_path if not missing_fields else f"{relative_path}:{','.join(missing_fields)}"
            )
    verdict_missing = [] if verdict_present else [*verdict_missing_candidates, "no_authoritative_contract_verdict_surface"]

    mar_complete = run_outcome_present and turn_capture_present and authored_output_present and verdict_present
    replay_ready = mar_complete and turn_capture_present
    stability_status = "not_evaluable"

    return {
        "workspace": str(workspace_root),
        "session_id": str(session_id),
        "run_status": str(summary.get("status") or ""),
        "mar_complete": mar_complete,
        "replay_ready": replay_ready,
        "stability_status": stability_status,
        "missing_evidence": [
            *run_outcome_missing,
            *turn_capture_missing,
            *authored_output_missing,
            *verdict_missing,
        ],
        "evidence_groups": {
            "run_outcome": {
                "present": run_outcome_present,
                "required_fields": list(required_run_fields),
                "missing": run_outcome_missing,
                "summary_path": run_summary_path.relative_to(workspace_root).as_posix(),
            },
            "turn_capture": {
                "present": turn_capture_present,
                "session_root_exists": session_root.exists(),
                "turn_count": len(turn_records),
                "turns": turn_rows,
                "missing": turn_capture_missing,
            },
            "authored_output": {
                "present": authored_output_present,
                "required_paths": required_authored_outputs,
                "missing": authored_output_missing,
            },
            "contract_verdict": {
                "present": verdict_present,
                "candidates": verdict_rows,
                "missing": verdict_missing,
            },
            "stability_evidence": {
                "present": False,
                "reason": "comparative_proof_absent",
                "stability_status": stability_status,
            },
        },
    }


def _collect_values_for_key(value: Any, key_name: str) -> set[str]:
    rows: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) == key_name:
                token = str(item or "").strip()
                if token:
                    rows.add(token)
            rows.update(_collect_values_for_key(item, key_name))
    elif isinstance(value, list):
        for item in value:
            rows.update(_collect_values_for_key(item, key_name))
    return rows


def build_identity_replacements(
    *,
    workspace: Path,
    session_id: str,
    turn_records: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    tokens: dict[str, str] = {}
    workspace_root = Path(workspace).resolve()
    workspace_name = workspace_root.name
    if workspace_name:
        tokens[workspace_name] = "__WORKSPACE__"
    session_token = str(session_id).strip()
    if session_token:
        tokens[session_token] = "__RUN_ID__"
    issue_ids = {
        str(row.get("issue_id") or "").strip()
        for row in turn_records
        if str(row.get("issue_id") or "").strip()
    }
    if isinstance(summary, dict):
        issue_ids.update(_collect_values_for_key(summary, "issue_id"))
    issue_ids = sorted(issue_ids)
    for index, issue_id in enumerate(issue_ids):
        tokens[issue_id] = f"__ISSUE_{index}__"
    rows = sorted(tokens.items(), key=lambda item: len(item[0]), reverse=True)
    return [(raw, replacement) for raw, replacement in rows if raw]


def replace_identity_tokens(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {str(key): replace_identity_tokens(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_identity_tokens(item, replacements) for item in value]
    if isinstance(value, str):
        text = normalize_text(value)
        for raw, replacement in replacements:
            text = text.replace(raw, replacement)
        return text
    return value


def drop_volatile_keys(value: Any, keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            str(key): drop_volatile_keys(item, keys)
            for key, item in value.items()
            if str(key) not in keys
        }
    if isinstance(value, list):
        return [drop_volatile_keys(item, keys) for item in value]
    return value


def normalize_json_surface(value: Any, *, surface_kind: str, replacements: list[tuple[str, str]]) -> Any:
    replaced = replace_identity_tokens(value, replacements)
    keys = set(COMMON_VOLATILE_KEYS) | set(SURFACE_VOLATILE_KEYS.get(surface_kind, set()))
    pruned = drop_volatile_keys(replaced, keys)
    return odr_canonicalize(pruned)


def surface_digest(value: Any) -> str:
    if isinstance(value, str):
        return sha256_text(value)
    return json_sha256(value)


def text_diff_location(left: str, right: str) -> dict[str, Any]:
    left_text = normalize_text(left)
    right_text = normalize_text(right)
    if left_text == right_text:
        return {"path": "$", "line": 1, "column": 1}
    line = 1
    column = 1
    for left_char, right_char in zip(left_text, right_text):
        if left_char != right_char:
            return {"path": "$", "line": line, "column": column}
        if left_char == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return {"path": "$", "line": line, "column": column}


def write_report(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return write_payload_with_diff_ledger(Path(path), payload)
