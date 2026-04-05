from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


DEFAULT_CORPUS = Path("docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json")
DEFAULT_OUTPUT = Path("benchmarks/staging/General/prompt_reforger_gemma_tool_use_score.json")


@dataclass(frozen=True)
class SliceSpec:
    slice_id: str
    issue_id: str
    role_name: str
    description: str
    required_action_tools: tuple[str, ...]
    required_read_paths: tuple[str, ...]
    required_write_paths: tuple[str, ...]
    required_statuses: tuple[str, ...]
    preconditions: tuple[str, ...]
    postconditions: tuple[str, ...]


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _relativize(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_corpus(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("corpus must be a JSON object")
    return payload


def _slice_specs(payload: dict[str, Any]) -> list[SliceSpec]:
    raw_slices = payload.get("slices")
    if not isinstance(raw_slices, list):
        raise ValueError("corpus.slices must be a list")
    specs: list[SliceSpec] = []
    for row in raw_slices:
        if not isinstance(row, dict):
            raise ValueError("corpus slice must be an object")
        specs.append(
            SliceSpec(
                slice_id=str(row.get("slice_id") or ""),
                issue_id=str(row.get("issue_id") or "").upper(),
                role_name=str(row.get("role_name") or ""),
                description=str(row.get("description") or ""),
                required_action_tools=tuple(str(item) for item in (row.get("required_action_tools") or [])),
                required_read_paths=tuple(str(item) for item in (row.get("required_read_paths") or [])),
                required_write_paths=tuple(str(item) for item in (row.get("required_write_paths") or [])),
                required_statuses=tuple(str(item).strip().lower() for item in (row.get("required_statuses") or [])),
                preconditions=tuple(str(item) for item in (row.get("preconditions") or [])),
                postconditions=tuple(str(item) for item in (row.get("postconditions") or [])),
            )
        )
    return specs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score one challenge_workflow_runtime run against the bounded Gemma tool-use corpus.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--run-summary", required=True)
    parser.add_argument("--observability-root", required=True)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    return parser


def _role_from_turn_dir(dirname: str) -> str:
    parts = dirname.split("_", 1)
    return parts[1] if len(parts) == 2 else ""


def _turn_index(dirname: str) -> int:
    parts = dirname.split("_", 1)
    try:
        return int(parts[0])
    except (IndexError, ValueError):
        return 10**9


def _collect_turns(observability_root: Path, repo_root: Path) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    if not observability_root.exists():
        return turns
    for issue_dir in sorted([path for path in observability_root.iterdir() if path.is_dir()], key=lambda p: p.name.lower()):
        issue_id = issue_dir.name.upper()
        for turn_dir in sorted([path for path in issue_dir.iterdir() if path.is_dir()], key=lambda p: p.name.lower()):
            parsed_path = turn_dir / "parsed_tool_calls.json"
            diagnostics_path = turn_dir / "tool_parser_diagnostics.json"
            parsed_tool_calls = _read_json(parsed_path) if parsed_path.exists() else []
            tool_parser_diagnostics = _read_json(diagnostics_path) if diagnostics_path.exists() else []
            turns.append(
                {
                    "issue_id": issue_id,
                    "role_name": _role_from_turn_dir(turn_dir.name),
                    "turn_dir": turn_dir.name,
                    "turn_index": _turn_index(turn_dir.name),
                    "parsed_tool_calls": parsed_tool_calls if isinstance(parsed_tool_calls, list) else [],
                    "tool_parser_diagnostics": tool_parser_diagnostics if isinstance(tool_parser_diagnostics, list) else [],
                    "messages_ref": _relativize(turn_dir / "messages.json", repo_root),
                    "prompt_layers_ref": _relativize(turn_dir / "prompt_layers.json", repo_root),
                    "model_response_ref": _relativize(turn_dir / "model_response.txt", repo_root),
                    "model_response_raw_ref": _relativize(turn_dir / "model_response_raw.json", repo_root),
                    "parsed_tool_calls_ref": _relativize(parsed_path, repo_root),
                    "tool_parser_diagnostics_ref": _relativize(diagnostics_path, repo_root),
                }
            )
    return sorted(turns, key=lambda row: int(row["turn_index"]))


def _collect_prior_written_paths(turns: list[dict[str, Any]], *, before_turn_index: int) -> set[str]:
    written: set[str] = set()
    for turn in turns:
        if int(turn["turn_index"]) >= before_turn_index:
            break
        for call in turn.get("parsed_tool_calls") or []:
            if not isinstance(call, dict) or str(call.get("tool") or "") != "write_file":
                continue
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            path = str(args.get("path") or "").strip()
            if path:
                written.add(path)
    return written


def _evaluate_call(call: dict[str, Any], spec: SliceSpec) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    tool = str(call.get("tool") or "").strip()
    args = call.get("args") if isinstance(call.get("args"), dict) else {}
    if tool not in spec.required_action_tools:
        return None, {"tool": tool, "reason": "undeclared_tool", "args": args}, None
    if tool == "write_file":
        path = str(args.get("path") or "").strip()
        content = args.get("content")
        if not path:
            defect = {"tool": tool, "field": "path", "reason": "missing_path", "args": args}
            return None, {"tool": tool, "reason": "argument_shape_invalid", "args": args}, defect
        if spec.required_write_paths and path not in spec.required_write_paths:
            return None, {"tool": tool, "reason": "unexpected_write_path", "args": args}, None
        if not isinstance(content, str) or not content.strip():
            defect = {"tool": tool, "field": "content", "reason": "empty_content", "args": args}
            return None, {"tool": tool, "reason": "argument_shape_invalid", "args": args}, defect
    elif tool == "read_file":
        path = str(args.get("path") or "").strip()
        if not path:
            defect = {"tool": tool, "field": "path", "reason": "missing_path", "args": args}
            return None, {"tool": tool, "reason": "argument_shape_invalid", "args": args}, defect
        if spec.required_read_paths and path not in spec.required_read_paths:
            return None, {"tool": tool, "reason": "unexpected_read_path", "args": args}, None
    elif tool == "update_issue_status":
        status = str(args.get("status") or "").strip().lower()
        if not status:
            defect = {"tool": tool, "field": "status", "reason": "missing_status", "args": args}
            return None, {"tool": tool, "reason": "argument_shape_invalid", "args": args}, defect
        if spec.required_statuses and status not in spec.required_statuses:
            return None, {"tool": tool, "reason": "unexpected_status", "args": args}, None
    return {"tool": tool, "args": args}, None, None


def _diagnostic_rejections(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for row in diagnostics:
        if not isinstance(row, dict):
            continue
        stage = str(row.get("stage") or "").strip()
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        if stage == "native_tool_call_skipped":
            rejected.append(
                {
                    "tool": str(data.get("tool") or ""),
                    "reason": str(data.get("reason") or "skipped_native_tool"),
                    "diagnostic_stage": stage,
                }
            )
    return rejected


def _evaluate_turn(turn: dict[str, Any], spec: SliceSpec) -> dict[str, Any]:
    accepted_calls: list[dict[str, Any]] = []
    rejected_calls: list[dict[str, Any]] = []
    argument_shape_defects: list[dict[str, Any]] = []
    for call in turn.get("parsed_tool_calls") or []:
        if not isinstance(call, dict):
            continue
        accepted, rejected, defect = _evaluate_call(call, spec)
        if accepted:
            accepted_calls.append(accepted)
        if rejected:
            rejected_calls.append(rejected)
        if defect:
            argument_shape_defects.append(defect)
    rejected_calls.extend(_diagnostic_rejections(turn.get("tool_parser_diagnostics") or []))

    seen_tools = {call["tool"] for call in accepted_calls}
    seen_write_paths = {
        str(call["args"].get("path") or "").strip()
        for call in accepted_calls
        if call["tool"] == "write_file"
    }
    seen_read_paths = {
        str(call["args"].get("path") or "").strip()
        for call in accepted_calls
        if call["tool"] == "read_file"
    }
    seen_statuses = {
        str(call["args"].get("status") or "").strip().lower()
        for call in accepted_calls
        if call["tool"] == "update_issue_status"
    }
    required_reads_met = True
    if "read_file" in spec.required_action_tools:
        required_reads_met = set(spec.required_read_paths).issubset(seen_read_paths)
    required_writes_met = True
    if "write_file" in spec.required_action_tools:
        required_writes_met = set(spec.required_write_paths).issubset(seen_write_paths)
    required_statuses_met = True
    if "update_issue_status" in spec.required_action_tools:
        required_statuses_met = set(spec.required_statuses).issubset(seen_statuses)
    valid_completion = (
        set(spec.required_action_tools).issubset(seen_tools)
        and required_reads_met
        and required_writes_met
        and required_statuses_met
    )
    return {
        "turn_dir": turn["turn_dir"],
        "turn_index": turn["turn_index"],
        "accepted_tool_calls": accepted_calls,
        "rejected_tool_calls": rejected_calls,
        "argument_shape_defects": argument_shape_defects,
        "valid_completion": valid_completion,
        "messages_ref": turn["messages_ref"],
        "prompt_layers_ref": turn["prompt_layers_ref"],
        "model_response_ref": turn["model_response_ref"],
        "model_response_raw_ref": turn["model_response_raw_ref"],
        "parsed_tool_calls_ref": turn["parsed_tool_calls_ref"],
        "tool_parser_diagnostics_ref": turn["tool_parser_diagnostics_ref"],
    }


def _repair_turn_indexes(run_summary: dict[str, Any]) -> dict[str, list[int]]:
    cards_runtime = run_summary.get("cards_runtime") if isinstance(run_summary.get("cards_runtime"), dict) else {}
    packet2 = run_summary.get("truthful_runtime_packet2") if isinstance(run_summary.get("truthful_runtime_packet2"), dict) else {}
    repair_block = packet2.get("repair_ledger") if isinstance(packet2.get("repair_ledger"), dict) else {}
    if not repair_block:
        repair_block = cards_runtime.get("repair_ledger") if isinstance(cards_runtime.get("repair_ledger"), dict) else {}
    entries = repair_block.get("entries") if isinstance(repair_block.get("entries"), list) else []
    by_issue: dict[str, list[int]] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        issue_id = str(row.get("issue_id") or "").strip().upper()
        turn_index = int(row.get("turn_index") or 0)
        if issue_id and turn_index > 0:
            by_issue.setdefault(issue_id, []).append(turn_index)
    return by_issue


def _score_slice(spec: SliceSpec, turns: list[dict[str, Any]], repair_turns: dict[str, list[int]]) -> dict[str, Any]:
    matching_turns = [turn for turn in turns if turn["issue_id"] == spec.issue_id and turn["role_name"] == spec.role_name]
    evaluated_turns = [_evaluate_turn(turn, spec) for turn in matching_turns]
    first_tool_turn = next((row["turn_index"] for row in evaluated_turns if row["accepted_tool_calls"]), None)
    first_completion_turn = next((row["turn_index"] for row in evaluated_turns if row["valid_completion"]), None)
    prior_writes = _collect_prior_written_paths(turns, before_turn_index=int(matching_turns[0]["turn_index"])) if matching_turns else set()
    precondition_record = {
        "declared_preconditions": list(spec.preconditions),
        "required_read_paths": list(spec.required_read_paths),
        "required_read_paths_written_before_slice": sorted(set(spec.required_read_paths).intersection(prior_writes)),
        "required_read_paths_missing_before_slice": sorted(set(spec.required_read_paths).difference(prior_writes)),
    }
    seen_write_paths = sorted(
        {
            str(call["args"].get("path") or "").strip()
            for turn in evaluated_turns
            for call in turn["accepted_tool_calls"]
            if call["tool"] == "write_file"
        }
    )
    seen_read_paths = sorted(
        {
            str(call["args"].get("path") or "").strip()
            for turn in evaluated_turns
            for call in turn["accepted_tool_calls"]
            if call["tool"] == "read_file"
        }
    )
    seen_statuses = sorted(
        {
            str(call["args"].get("status") or "").strip().lower()
            for turn in evaluated_turns
            for call in turn["accepted_tool_calls"]
            if call["tool"] == "update_issue_status"
        }
    )
    postcondition_record = {
        "declared_postconditions": list(spec.postconditions),
        "required_write_paths": list(spec.required_write_paths),
        "observed_write_paths": seen_write_paths,
        "required_read_paths": list(spec.required_read_paths),
        "observed_read_paths": seen_read_paths,
        "required_statuses": list(spec.required_statuses),
        "observed_statuses": seen_statuses,
    }
    if not evaluated_turns:
        final_disposition = "not_exercised"
    elif first_completion_turn is not None and repair_turns.get(spec.issue_id):
        final_disposition = "accepted_with_repair"
    elif first_completion_turn is not None:
        final_disposition = "accepted_direct"
    elif first_tool_turn is not None:
        final_disposition = "partial_contract_match"
    else:
        final_disposition = "rejected"
    return {
        "slice_id": spec.slice_id,
        "issue_id": spec.issue_id,
        "role_name": spec.role_name,
        "description": spec.description,
        "required_action_tools": list(spec.required_action_tools),
        "required_read_paths": list(spec.required_read_paths),
        "required_write_paths": list(spec.required_write_paths),
        "required_statuses": list(spec.required_statuses),
        "turns_to_first_valid_tool_call": first_tool_turn,
        "turns_to_first_valid_completion": first_completion_turn,
        "final_disposition": final_disposition,
        "precondition_record": precondition_record,
        "postcondition_record": postcondition_record,
        "evaluated_turns": evaluated_turns,
    }


def score_corpus(*, corpus: dict[str, Any], run_summary: dict[str, Any], observability_root: Path, repo_root: Path) -> dict[str, Any]:
    specs = _slice_specs(corpus)
    turns = _collect_turns(observability_root, repo_root)
    repair_turns = _repair_turn_indexes(run_summary)
    slice_results = [_score_slice(spec, turns, repair_turns) for spec in specs]
    accepted = sum(1 for row in slice_results if row["final_disposition"] in {"accepted_direct", "accepted_with_repair"})
    exercised = sum(1 for row in slice_results if row["final_disposition"] != "not_exercised")
    partial = sum(1 for row in slice_results if row["final_disposition"] == "partial_contract_match")
    observed_path = "blocked"
    observed_result = "failure"
    if exercised > 0:
        observed_path = "primary"
        if accepted == len(slice_results):
            observed_result = "success"
        elif accepted > 0 or partial > 0:
            observed_result = "partial success"
    return {
        "schema_version": "prompt_reforger_gemma_tool_use_score.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "structural",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "corpus_id": str(corpus.get("corpus_id") or ""),
        "implementation_plan_ref": str(corpus.get("implementation_plan_ref") or ""),
        "epic_ref": str(corpus.get("epic_ref") or ""),
        "judge_protocol_ref": str(corpus.get("judge_protocol_ref") or ""),
        "source_run": {
            "run_id": str(run_summary.get("run_id") or ""),
            "status": str(run_summary.get("status") or ""),
            "stop_reason": str(run_summary.get("stop_reason") or ""),
            "run_summary_ref": "",
            "observability_root_ref": _relativize(observability_root, repo_root),
        },
        "scoreboard": {
            "slices_total": len(slice_results),
            "slices_exercised": exercised,
            "accepted_slices": accepted,
            "repaired_slices": sum(1 for row in slice_results if row["final_disposition"] == "accepted_with_repair"),
            "partial_slices": partial,
            "rejected_slices": sum(1 for row in slice_results if row["final_disposition"] == "rejected"),
            "not_exercised_slices": sum(1 for row in slice_results if row["final_disposition"] == "not_exercised"),
        },
        "slice_results": slice_results,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    run_summary_path = _resolve_repo_path(repo_root, str(args.run_summary))
    observability_root = _resolve_repo_path(repo_root, str(args.observability_root))
    corpus_path = _resolve_repo_path(repo_root, str(args.corpus))
    out_path = _resolve_repo_path(repo_root, str(args.out))

    corpus = _load_corpus(corpus_path)
    run_summary = _read_json(run_summary_path)
    if not isinstance(run_summary, dict):
        raise ValueError("run summary must be a JSON object")
    payload = score_corpus(corpus=corpus, run_summary=run_summary, observability_root=observability_root, repo_root=repo_root)
    payload["source_run"]["run_summary_ref"] = _relativize(run_summary_path, repo_root)
    write_payload_with_diff_ledger(out_path, payload)
    print(
        json.dumps(
            {
                "corpus_id": str(payload.get("corpus_id") or ""),
                "observed_path": str(payload.get("observed_path") or ""),
                "observed_result": str(payload.get("observed_result") or ""),
                "out": _relativize(out_path, repo_root),
            }
        )
    )
    return 0 if str(payload.get("observed_path") or "") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
