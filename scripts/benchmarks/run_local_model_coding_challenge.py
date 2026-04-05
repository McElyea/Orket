from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.common.run_summary_support import load_validated_run_summary_or_empty
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger
    from common.run_summary_support import load_validated_run_summary_or_empty


DEFAULT_OUTPUT = Path("benchmarks/staging/General/local_model_coding_challenge_report.json")
DEFAULT_WORKSPACE_ROOT = Path(".tmp/local_model_coding_challenge")
_ISSUE_DIR_PATTERN = re.compile(r"^cwr-(\d+)$", re.IGNORECASE)
_TURN_DIR_PATTERN = re.compile(r"^(\d+)_")


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local provider/model through a coding challenge epic repeatedly and write a compact scoreboard."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--epic", default="challenge_workflow_runtime")
    parser.add_argument("--provider", default=os.getenv("ORKET_LLM_PROVIDER", "lmstudio"))
    parser.add_argument("--model", default="google/gemma-4-26b-a4b")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--workspace-root", default=str(DEFAULT_WORKSPACE_ROOT))
    parser.add_argument("--build-id-prefix", default="local_model_coding_challenge")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--prompt-patch-file", default="")
    parser.add_argument("--prompt-patch-label", default="")
    return parser


def _resolve_repo_path(repo_root: Path, raw_path: str) -> Path:
    candidate = Path(str(raw_path))
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _relativize(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_prompt_patch(repo_root: Path, raw_path: str) -> tuple[str, str]:
    patch_path = str(raw_path or "").strip()
    if not patch_path:
        return "", ""
    resolved_path = _resolve_repo_path(repo_root, patch_path)
    return resolved_path.read_text(encoding="utf-8"), _relativize(resolved_path, repo_root)


def _issue_sort_key(path: Path) -> tuple[int, str]:
    match = _ISSUE_DIR_PATTERN.match(path.name)
    if match is None:
        return (10**9, path.name.lower())
    return (int(match.group(1)), path.name.lower())


def _turn_sort_key(path: Path) -> tuple[int, str]:
    match = _TURN_DIR_PATTERN.match(path.name)
    if match is None:
        return (10**9, path.name.lower())
    return (int(match.group(1)), path.name.lower())


def _issue_id_from_dirname(dirname: str) -> str:
    match = _ISSUE_DIR_PATTERN.match(dirname)
    if match is None:
        return dirname.upper()
    return f"CWR-{int(match.group(1)):02d}"


def _reset_run_workspace(*, workspace_root: Path, run_workspace: Path) -> None:
    resolved_root = workspace_root.resolve()
    resolved_run = run_workspace.resolve()
    if resolved_run == resolved_root:
        raise ValueError("workspace_run_dir_must_not_equal_workspace_root")
    if not resolved_run.is_relative_to(resolved_root):
        raise ValueError("workspace_run_dir_outside_workspace_root")
    if resolved_run.exists():
        shutil.rmtree(resolved_run)
    resolved_run.mkdir(parents=True, exist_ok=True)


def _load_json_list(path: Path) -> list[Any]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collect_observed_turns(run_observability_root: Path) -> list[dict[str, Any]]:
    if not run_observability_root.exists():
        return []
    observed_turns: list[dict[str, Any]] = []
    for issue_dir in sorted([path for path in run_observability_root.iterdir() if path.is_dir()], key=_issue_sort_key):
        issue_id = _issue_id_from_dirname(issue_dir.name)
        for turn_dir in sorted([path for path in issue_dir.iterdir() if path.is_dir()], key=_turn_sort_key):
            parsed_calls = _load_json_list(turn_dir / "parsed_tool_calls.json")
            observed_turns.append(
                {
                    "issue_id": issue_id,
                    "issue_dir": issue_dir.name,
                    "turn_dir": turn_dir.name,
                    "turn_index": _turn_sort_key(turn_dir)[0],
                    "parsed_tool_calls": parsed_calls,
                    "messages_path": turn_dir / "messages.json",
                }
            )
    return observed_turns


def _first_write_turn(observed_turns: list[dict[str, Any]], *, program_only: bool) -> dict[str, Any] | None:
    for turn in observed_turns:
        write_paths: list[str] = []
        for call in turn.get("parsed_tool_calls") or []:
            if not isinstance(call, dict):
                continue
            if str(call.get("tool") or "").strip() != "write_file":
                continue
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            path = str(args.get("path") or "").strip()
            if not path:
                continue
            if program_only and not path.endswith(".py"):
                continue
            write_paths.append(path)
        if write_paths:
            return {
                "issue_id": turn["issue_id"],
                "turn_dir": turn["turn_dir"],
                "turn_index": turn["turn_index"],
                "paths": write_paths,
            }
    return None


def _collect_written_paths(observed_turns: list[dict[str, Any]], *, program_only: bool) -> list[str]:
    written_paths: set[str] = set()
    for turn in observed_turns:
        for call in turn.get("parsed_tool_calls") or []:
            if not isinstance(call, dict):
                continue
            if str(call.get("tool") or "").strip() != "write_file":
                continue
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            path = str(args.get("path") or "").strip()
            if not path:
                continue
            if program_only and not path.endswith(".py"):
                continue
            written_paths.add(path)
    return sorted(written_paths)


def _collect_model_written_program_hashes(workspace: Path, observed_turns: list[dict[str, Any]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative_path in _collect_written_paths(observed_turns, program_only=True):
        if not relative_path.startswith("agent_output/"):
            continue
        file_path = workspace / relative_path
        if not file_path.is_file():
            continue
        hashes[relative_path.removeprefix("agent_output/")] = _read_file_hash(file_path)
    return hashes


def _find_latest_retry_note(observed_turns: list[dict[str, Any]]) -> str:
    for turn in reversed(observed_turns):
        for message in _load_json_list(Path(turn["messages_path"])):
            if not isinstance(message, dict):
                continue
            content = str(message.get("content") or "")
            for line in reversed(content.splitlines()):
                trimmed = line.strip()
                if trimmed.startswith("Retry Note:"):
                    return trimmed.partition(":")[2].strip()
                if "runtime_guard_retry_scheduled:" in trimmed:
                    return trimmed.partition("runtime_guard_retry_scheduled:")[2].strip()
                if trimmed.startswith("Corrective instruction:"):
                    return trimmed.partition(":")[2].strip()
    return ""


def _classify_blocker(*, note: str, repair_ledger: list[dict[str, Any]], status: str, stop_reason: str) -> str:
    normalized = note.lower()
    if "runtime stdout assertion failed" in normalized:
        return "runtime_stdout_assertion_failed"
    if "progress contract not met after corrective reprompt" in normalized:
        return "progress_contract_not_met_after_corrective_reprompt"
    if "artifact semantic contract not met" in normalized:
        return "artifact_semantic_contract_not_met"
    for row in reversed(repair_ledger):
        reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
        for reason in reasons:
            token = str(reason or "").strip()
            if token:
                return token
    if stop_reason:
        return stop_reason
    if status:
        return status
    return "unknown"


def _find_run_summary(workspace: Path) -> tuple[Path | None, dict[str, Any]]:
    run_root = workspace / "runs"
    if not run_root.exists():
        return None, {}
    candidates = sorted(
        [path for path in run_root.glob("*/run_summary.json") if path.is_file()],
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        payload = load_validated_run_summary_or_empty(path)
        if payload:
            return path, payload
    return None, {}


def _build_run_command(
    *,
    repo_root: Path,
    python_bin: str,
    epic: str,
    workspace: Path,
    build_id: str,
    model: str,
) -> list[str]:
    workspace_arg = _relativize(workspace, repo_root)
    return [
        python_bin,
        "main.py",
        "--epic",
        epic,
        "--workspace",
        workspace_arg,
        "--build-id",
        build_id,
        "--model",
        model,
    ]


def _execute_challenge_run(
    *,
    repo_root: Path,
    python_bin: str,
    epic: str,
    provider: str,
    model: str,
    workspace: Path,
    build_id: str,
    prompt_patch: str,
    prompt_patch_label: str,
) -> dict[str, Any]:
    command = _build_run_command(
        repo_root=repo_root,
        python_bin=python_bin,
        epic=epic,
        workspace=workspace,
        build_id=build_id,
        model=model,
    )
    env = os.environ.copy()
    env["ORKET_DISABLE_SANDBOX"] = "1"
    env["ORKET_LLM_PROVIDER"] = provider
    if prompt_patch:
        env["ORKET_PROMPT_PATCH"] = prompt_patch
    else:
        env.pop("ORKET_PROMPT_PATCH", None)
    if prompt_patch_label:
        env["ORKET_PROMPT_PATCH_LABEL"] = prompt_patch_label
    else:
        env.pop("ORKET_PROMPT_PATCH_LABEL", None)
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "command": command,
        "exit_code": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
    }


def _summarize_run(
    *,
    repo_root: Path,
    workspace: Path,
    epic: str,
    provider: str,
    model: str,
    run_ordinal: int,
    execution: dict[str, Any],
) -> dict[str, Any]:
    summary_path, run_summary = _find_run_summary(workspace)
    run_id = str(run_summary.get("run_id") or "").strip()
    status = str(run_summary.get("status") or "").strip()
    stop_reason = str(run_summary.get("stop_reason") or "").strip()
    run_observability_root = workspace / "observability" / run_id if run_id else workspace / "observability" / "_missing_run_id_"
    observed_turns = _collect_observed_turns(run_observability_root)
    deepest_issue = observed_turns[-1]["issue_id"] if observed_turns else ""
    first_artifact_write = _first_write_turn(observed_turns, program_only=False)
    first_program_write = _first_write_turn(observed_turns, program_only=True)
    cards_runtime = run_summary.get("cards_runtime") if isinstance(run_summary.get("cards_runtime"), dict) else {}
    packet2 = run_summary.get("truthful_runtime_packet2") if isinstance(run_summary.get("truthful_runtime_packet2"), dict) else {}
    repair_ledger_block = packet2.get("repair_ledger") if isinstance(packet2.get("repair_ledger"), dict) else {}
    if not repair_ledger_block:
        repair_ledger_block = cards_runtime.get("repair_ledger") if isinstance(cards_runtime.get("repair_ledger"), dict) else {}
    if repair_ledger_block:
        repair_ledger_raw = repair_ledger_block.get("entries") if isinstance(repair_ledger_block.get("entries"), list) else []
    else:
        repair_ledger_raw = cards_runtime.get("repair_ledger") if isinstance(cards_runtime.get("repair_ledger"), list) else []
    repair_ledger = [row for row in repair_ledger_raw if isinstance(row, dict)]
    blocker_note = _find_latest_retry_note(observed_turns)
    blocker_family = _classify_blocker(
        note=blocker_note,
        repair_ledger=repair_ledger,
        status=status,
        stop_reason=stop_reason,
    )
    program_hashes = _collect_model_written_program_hashes(workspace, observed_turns)
    challenge_result = "failure"
    if status == "done":
        challenge_result = "success"
    elif program_hashes or deepest_issue:
        challenge_result = "partial success"
    observed_path = "primary" if run_summary else "blocked"
    return {
        "run_ordinal": run_ordinal,
        "epic": epic,
        "provider": provider,
        "model": model,
        "workspace": _relativize(workspace, repo_root),
        "command": execution.get("command") or [],
        "command_exit_code": int(execution.get("exit_code") or 0),
        "run_id": run_id,
        "run_summary_path": _relativize(summary_path, repo_root) if summary_path is not None else "",
        "status": status or "summary_missing",
        "stop_reason": stop_reason,
        "observed_path": observed_path,
        "result": challenge_result,
        "deepest_issue": deepest_issue,
        "turn_count_observed": len(observed_turns),
        "first_artifact_write": first_artifact_write,
        "first_program_write": first_program_write,
        "program_file_hashes": program_hashes,
        "challenge_runtime_py_files": sorted(
            [path for path in program_hashes.keys() if path.startswith("challenge_runtime/")]
        ),
        "final_disposition": str(
            repair_ledger_block.get("final_disposition") or cards_runtime.get("final_disposition") or ""
        ).strip(),
        "repair_count": int(repair_ledger_block.get("repair_count") or cards_runtime.get("repair_count") or len(repair_ledger)),
        "repair_ledger": repair_ledger,
        "final_blocker_family": blocker_family,
        "final_blocker_note": blocker_note,
        "stdout_tail": str(execution.get("stdout") or "").splitlines()[-20:],
        "stderr_tail": str(execution.get("stderr") or "").splitlines()[-20:],
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 3)


def _turn_range(turns: list[int]) -> dict[str, int | None]:
    if not turns:
        return {"min": None, "max": None}
    return {"min": min(turns), "max": max(turns)}


def _build_scoreboard(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total_runs = len(runs)
    completed_runs = sum(1 for run in runs if run.get("status") == "done")
    code_write_runs = sum(1 for run in runs if isinstance(run.get("program_file_hashes"), dict) and run["program_file_hashes"])
    summary_runs = sum(1 for run in runs if str(run.get("run_id") or "").strip())
    first_artifact_turns = [
        int(run["first_artifact_write"]["turn_index"])
        for run in runs
        if isinstance(run.get("first_artifact_write"), dict) and isinstance(run["first_artifact_write"].get("turn_index"), int)
    ]
    first_program_turns = [
        int(run["first_program_write"]["turn_index"])
        for run in runs
        if isinstance(run.get("first_program_write"), dict) and isinstance(run["first_program_write"].get("turn_index"), int)
    ]
    deepest_issue_counts = Counter(str(run.get("deepest_issue") or "none") for run in runs)
    status_counts = Counter(str(run.get("status") or "unknown") for run in runs)
    final_disposition_counts = Counter(str(run.get("final_disposition") or "none") for run in runs)
    blocker_family_counts = Counter(str(run.get("final_blocker_family") or "unknown") for run in runs)
    hash_rows = [json.dumps(run.get("program_file_hashes") or {}, sort_keys=True) for run in runs if run.get("program_file_hashes")]
    program_paths = sorted(
        {
            str(path)
            for run in runs
            for path in (run.get("program_file_hashes") or {}).keys()
        }
    )
    return {
        "total_runs": total_runs,
        "run_summary_runs": summary_runs,
        "completed_runs": completed_runs,
        "completion_rate": _rate(completed_runs, total_runs),
        "code_write_runs": code_write_runs,
        "code_write_rate": _rate(code_write_runs, total_runs),
        "deepest_issue_counts": dict(sorted(deepest_issue_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "final_disposition_counts": dict(sorted(final_disposition_counts.items())),
        "blocker_family_counts": dict(sorted(blocker_family_counts.items())),
        "first_artifact_write_turn_range": _turn_range(first_artifact_turns),
        "first_program_write_turn_range": _turn_range(first_program_turns),
        "all_program_hashes_identical": bool(hash_rows) and len(set(hash_rows)) == 1,
        "program_file_paths_union": program_paths,
    }


def run_local_model_coding_challenge(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(str(args.repo_root)).resolve()
    workspace_root = _resolve_repo_path(repo_root, str(args.workspace_root))
    workspace_root.mkdir(parents=True, exist_ok=True)
    prompt_patch, prompt_patch_ref = _load_prompt_patch(repo_root, str(getattr(args, "prompt_patch_file", "") or ""))
    prompt_patch_label = str(getattr(args, "prompt_patch_label", "") or "").strip()
    prompt_patch_checksum = hashlib.sha256(prompt_patch.encode("utf-8")).hexdigest()[:16] if prompt_patch else ""
    runs: list[dict[str, Any]] = []
    for run_ordinal in range(1, max(1, int(args.runs)) + 1):
        run_workspace = workspace_root / f"run_{run_ordinal:02d}"
        _reset_run_workspace(workspace_root=workspace_root, run_workspace=run_workspace)
        build_id = f"{str(args.build_id_prefix).strip()}_run{run_ordinal:02d}"
        execution = _execute_challenge_run(
            repo_root=repo_root,
            python_bin=str(args.python_bin),
            epic=str(args.epic),
            provider=str(args.provider),
            model=str(args.model),
            workspace=run_workspace,
            build_id=build_id,
            prompt_patch=prompt_patch,
            prompt_patch_label=prompt_patch_label,
        )
        runs.append(
            _summarize_run(
                repo_root=repo_root,
                workspace=run_workspace,
                epic=str(args.epic),
                provider=str(args.provider),
                model=str(args.model),
                run_ordinal=run_ordinal,
                execution=execution,
            )
        )
    scoreboard = _build_scoreboard(runs)
    benchmark_status = "complete"
    if scoreboard["run_summary_runs"] == 0:
        benchmark_status = "blocked"
    elif int(scoreboard["run_summary_runs"]) < int(scoreboard["total_runs"]):
        benchmark_status = "partial"
    observed_path = "primary" if benchmark_status == "complete" else ("degraded" if benchmark_status == "partial" else "blocked")
    observed_result = "failure"
    if benchmark_status == "blocked":
        observed_result = "environment blocker"
    elif int(scoreboard["completed_runs"]) == int(scoreboard["total_runs"]) and int(scoreboard["total_runs"]) > 0:
        observed_result = "success"
    elif int(scoreboard["code_write_runs"]) > 0 or int(scoreboard["run_summary_runs"]) > 0:
        observed_result = "partial success"
    payload = {
        "schema_version": "local_model_coding_challenge_report.v1",
        "generated_at_utc": _now_utc_iso(),
        "proof_type": "live",
        "status": benchmark_status,
        "observed_path": observed_path,
        "observed_result": observed_result,
        "epic": str(args.epic),
        "provider": str(args.provider),
        "model": str(args.model),
        "runs_requested": int(args.runs),
        "workspace_root": _relativize(workspace_root, repo_root),
        "canonical_out": _relativize(_resolve_repo_path(repo_root, str(args.out)), repo_root),
        "command_environment": {
            "ORKET_DISABLE_SANDBOX": "1",
            "ORKET_LLM_PROVIDER": str(args.provider),
        },
        "scoreboard": scoreboard,
        "runs": runs,
    }
    if prompt_patch:
        payload["prompt_patch"] = {
            "applied": True,
            "label": prompt_patch_label or "runtime_patch",
            "checksum": prompt_patch_checksum,
            "source_ref": prompt_patch_ref,
        }
        payload["command_environment"]["ORKET_PROMPT_PATCH_LABEL"] = prompt_patch_label or "runtime_patch"
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(str(args.repo_root)).resolve()
    out_path = _resolve_repo_path(repo_root, str(args.out))
    payload = run_local_model_coding_challenge(args)
    write_payload_with_diff_ledger(out_path, payload)
    print(
        json.dumps(
            {
                "status": str(payload.get("status") or ""),
                "observed_result": str(payload.get("observed_result") or ""),
                "out": _relativize(out_path, repo_root),
            }
        )
    )
    return 0 if str(payload.get("status") or "") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
