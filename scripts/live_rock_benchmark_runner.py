from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_card_runner():
    module_path = Path(__file__).resolve().parent / "live_card_benchmark_runner.py"
    spec = importlib.util.spec_from_file_location("live_card_benchmark_runner", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load helper module at {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


card_runner = _load_card_runner()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one benchmark task through live Orket rock execution.")
    parser.add_argument("--task", required=True, help="Path to benchmark task JSON.")
    parser.add_argument("--venue", default="local-hardware")
    parser.add_argument("--flow", default="live-rock")
    parser.add_argument("--run-dir", default="", help="Workspace/run directory.")
    parser.add_argument("--runs-root", default="workspace/runs", help="Durable root for indexed run artifacts.")
    parser.add_argument("--department", default="core")
    return parser.parse_args()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse_runtime_roles(runtime_events_path: Path) -> set[str]:
    roles: set[str] = set()
    if not runtime_events_path.exists():
        return roles
    for line in runtime_events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = str(row.get("role", "")).strip()
        event = str(row.get("event", "")).strip()
        if role and event == "turn_complete":
            roles.add(role)
    return roles


def _resolve_effective_run_dir(run_dir: Path) -> Path:
    direct_main = run_dir / "agent_output" / "main.py"
    if direct_main.exists():
        return run_dir
    candidates = []
    for child in run_dir.iterdir():
        if not child.is_dir():
            continue
        marker = child / "agent_output" / "main.py"
        if marker.exists():
            candidates.append(child)
    if not candidates:
        return run_dir
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    args = _parse_args()
    task_path = Path(args.task)
    task = json.loads(task_path.read_text(encoding="utf-8-sig"))
    task_id = str(task.get("id", "unknown"))
    task_id_padded = str(task_id).zfill(3) if str(task_id).isdigit() else str(task_id)
    started_at = _utc_now()
    run_id = uuid.uuid4().hex[:8]

    run_dir = Path(args.run_dir) if args.run_dir else task_path.parent
    run_dir.mkdir(parents=True, exist_ok=True)
    runs_root = Path(args.runs_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    canonical_name = f"{started_at.strftime('%Y%m%d_%H%M%S')}_task{task_id_padded}_{run_id}_rock"
    canonical_run_dir = runs_root / canonical_name
    canonical_run_dir.mkdir(parents=True, exist_ok=True)
    run_manifest_path = runs_root.parent / "run_manifest.jsonl"

    task_context_path = run_dir / "task_context.json"
    problem_statement_path = run_dir / "problem_statement.json"
    output_file = f"benchmark_task_{task_id}_output.md"
    task_context_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    problem_statement_path.write_text(
        json.dumps(
            {
                "id": task.get("id"),
                "description": task.get("description"),
                "problem": task.get("problem"),
                "function_signature": task.get("function_signature"),
                "constraints": task.get("constraints") or [],
                "io_examples": task.get("io_examples") or [],
                "instruction": task.get("instruction"),
                "evaluation": task.get("evaluation") or {},
                "acceptance_contract": task.get("acceptance_contract") or {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    epic_name = f"benchmark_live_{task_id}_{uuid.uuid4().hex[:8]}"
    rock_name = f"benchmark_live_rock_{task_id}_{uuid.uuid4().hex[:8]}"
    epic_path = Path("model") / str(args.department) / "epics" / f"{epic_name}.json"
    rock_path = Path("model") / str(args.department) / "rocks" / f"{rock_name}.json"

    epic_payload = card_runner._build_epic(  # noqa: SLF001 - intentional reuse of tested helper
        task=task,
        task_context_file=task_context_path.name,
        output_file=output_file,
    )
    epic_payload["name"] = epic_name
    rock_payload = {
        "name": rock_name,
        "description": f"Live benchmark rock for task {task_id}",
        "status": "ready",
        "owner_department": str(args.department),
        "epics": [{"department": str(args.department), "epic": epic_name}],
    }

    epic_path.parent.mkdir(parents=True, exist_ok=True)
    rock_path.parent.mkdir(parents=True, exist_ok=True)
    epic_path.write_text(json.dumps(epic_payload, indent=2) + "\n", encoding="utf-8")
    rock_path.write_text(json.dumps(rock_payload, indent=2) + "\n", encoding="utf-8")

    _append_jsonl(
        canonical_run_dir / "runtime_lifecycle.jsonl",
        {
            "event": "run_registered",
            "at_utc": _iso_z(started_at),
            "run_id": run_id,
            "task_id": task_id,
            "workspace": str(run_dir).replace("\\", "/"),
            "rock": rock_name,
            "epic": epic_name,
        },
    )

    cmd = [
        "python",
        "main.py",
        "--rock",
        rock_name,
        "--department",
        str(args.department),
        "--workspace",
        str(run_dir),
    ]

    env = dict(os.environ)
    env.setdefault("ORKET_DISABLE_SANDBOX", "1")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    finally:
        try:
            epic_path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            rock_path.unlink(missing_ok=True)
        except OSError:
            pass

    (run_dir / "live_runner_output.log").write_text(
        ((result.stdout or "") + "\n" + (result.stderr or "")).strip() + "\n",
        encoding="utf-8",
    )

    ended_at = _utc_now()
    effective_run_dir = _resolve_effective_run_dir(run_dir)
    orket_log_path = effective_run_dir / "orket.log"
    session_id = card_runner._parse_session_id(orket_log_path)  # noqa: SLF001
    quality_checks = card_runner._materialize_required_artifacts(  # noqa: SLF001
        run_dir=effective_run_dir,
        task=task,
        task_id=task_id,
        output_file=output_file,
        process_exit_code=int(result.returncode),
        started_at=started_at,
        ended_at=ended_at,
    )
    validation_issues = card_runner._validate_task_outputs(  # noqa: SLF001
        run_dir=effective_run_dir,
        task=task,
        output_file=output_file,
    )

    runtime_roles = _parse_runtime_roles(effective_run_dir / "agent_output" / "observability" / "runtime_events.jsonl")
    if "coder" not in runtime_roles:
        validation_issues.append("missing completed coder turn in runtime events")
    if not any(role in runtime_roles for role in {"integrity_guard", "code_reviewer"}):
        validation_issues.append("missing completed reviewer/guard turn in runtime events")

    validation_passed = len(validation_issues) == 0 and int(result.returncode) == 0
    final_exit_code = 0 if validation_passed else 2

    final_main_path = effective_run_dir / "agent_output" / "main.py"
    final_main_text = final_main_path.read_text(encoding="utf-8", errors="replace") if final_main_path.exists() else ""
    coder_final_message = card_runner._extract_coder_final_message(  # noqa: SLF001
        run_dir=effective_run_dir,
        session_id=session_id,
        task_id=task_id_padded,
    )

    runtime_event_payload = {
        "schema_version": "v1",
        "event": "coder_turn_finalized",
        "role": "system",
        "session_id": session_id,
        "issue_id": f"LB-{task_id_padded}-1",
        "turn_index": 0,
        "turn_trace_id": "",
        "selected_model": "",
        "prompt_id": "",
        "prompt_version": "",
        "prompt_checksum": "",
        "resolver_policy": "",
        "selection_policy": "",
        "guard_contract": None,
        "guard_decision": None,
        "terminal_reason": None,
        "duration_ms": int((ended_at - started_at).total_seconds() * 1000.0),
        "tokens": None,
    }
    _append_jsonl(canonical_run_dir / "runtime_lifecycle.jsonl", runtime_event_payload)
    _append_jsonl(
        canonical_run_dir / "runtime_lifecycle.jsonl",
        {
            "event": "run_artifacts_persisted",
            "at_utc": _iso_z(ended_at),
            "run_id": run_id,
            "task_id": task_id,
            "canonical_run_dir": str(canonical_run_dir).replace("\\", "/"),
        },
    )
    _append_jsonl(effective_run_dir / "agent_output" / "observability" / "runtime_events.jsonl", runtime_event_payload)

    card_runner._safe_copy(task_context_path, canonical_run_dir / "task_context.json")  # noqa: SLF001
    card_runner._safe_copy(problem_statement_path, canonical_run_dir / "problem_statement.json")  # noqa: SLF001
    card_runner._safe_copy(run_dir / "live_runner_output.log", canonical_run_dir / "live_runner_output.log")  # noqa: SLF001
    card_runner._safe_copy(orket_log_path, canonical_run_dir / "orket.log")  # noqa: SLF001
    card_runner._safe_copy(final_main_path, canonical_run_dir / "coder_final_main.py")  # noqa: SLF001
    if coder_final_message:
        (canonical_run_dir / "coder_final_message.txt").write_text(coder_final_message, encoding="utf-8")
    card_runner._safe_copy_tree(effective_run_dir / "observability", canonical_run_dir / "observability")  # noqa: SLF001
    card_runner._safe_copy_tree(effective_run_dir / "agent_output" / "verification", canonical_run_dir / "verification")  # noqa: SLF001

    run_meta: dict[str, Any] = {
        "run_id": run_id,
        "session_id": session_id,
        "task_id": task_id,
        "issue_id": f"LB-{task_id_padded}-1",
        "started_at_utc": _iso_z(started_at),
        "ended_at_utc": _iso_z(ended_at),
        "duration_ms": int((ended_at - started_at).total_seconds() * 1000.0),
        "status": "passed" if validation_passed else "failed",
        "validation_passed": validation_passed,
        "validation_issues": validation_issues,
        "quality_checks": quality_checks,
        "workspace": str(run_dir).replace("\\", "/"),
        "effective_workspace": str(effective_run_dir).replace("\\", "/"),
        "canonical_run_dir": str(canonical_run_dir).replace("\\", "/"),
        "observability_path": str(canonical_run_dir / "observability" / session_id).replace("\\", "/")
        if session_id
        else "",
        "epic": epic_name,
        "rock": rock_name,
        "run_mode": "rock",
        "runtime_roles": sorted(runtime_roles),
        "model_map": {},
        "prompt_checksum": "",
        "venue": str(args.venue),
        "flow": str(args.flow),
        "department": str(args.department),
        "output_file": output_file,
        "final_main_path": str(canonical_run_dir / "coder_final_main.py").replace("\\", "/"),
    }
    if final_main_text:
        run_meta["final_main_sha256"] = hashlib.sha256(final_main_text.encode("utf-8")).hexdigest()

    (canonical_run_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2) + "\n", encoding="utf-8")
    _append_jsonl(run_manifest_path, run_meta)

    print(
        json.dumps(
            {
                "task_id": task_id,
                "exit_code": final_exit_code,
                "workspace": str(run_dir).replace("\\", "/"),
                "canonical_run_dir": str(canonical_run_dir).replace("\\", "/"),
                "run_manifest": str(run_manifest_path).replace("\\", "/"),
                "run_id": run_id,
                "session_id": session_id,
                "rock": rock_name,
                "epic": epic_name,
                "output_file": output_file,
                "validation_passed": validation_passed,
                "validation_issues": validation_issues,
            },
            sort_keys=True,
        )
    )
    return final_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
