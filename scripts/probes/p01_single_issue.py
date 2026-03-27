from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.core.cards_runtime_contract import APP_EXECUTION_PROFILE, ARTIFACT_EXECUTION_PROFILE
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.runtime.execution_pipeline import ExecutionPipeline
from scripts.probes.probe_support import (
    applied_probe_env,
    collect_artifact_hits,
    is_environment_blocker,
    json_safe,
    now_utc_iso,
    protocol_events,
    run_summary,
    runtime_events,
    write_probe_runtime_root,
    write_report,
    workspace_log_records,
)

EPIC_ID = "probe-p01-single-issue"
ISSUE_ID = "P01-FIB-01"
DEFAULT_SESSION_ID = "probe-p01-single-issue"
DEFAULT_BUILD_ID = "build-probe-p01-single-issue"
DEFAULT_OUTPUT = "benchmarks/results/probes/p01_single_issue.json"
DEFAULT_REQUESTED_ARTIFACT = "agent_output/fibonacci.py"
ARTIFACT_NAMES = (
    "messages.json",
    "model_response.txt",
    "model_response_raw.json",
    "parsed_tool_calls.json",
    "checkpoint.json",
)


def _safe_token(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()).strip("-") or "probe"


def _workspace_token(workspace: Path) -> str:
    resolved = str(workspace.resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:10]
    return f"{_safe_token(workspace.name)}-{digest}"


def _effective_session_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.session_id) != DEFAULT_SESSION_ID:
        return str(args.session_id)
    return f"{DEFAULT_SESSION_ID}-{_workspace_token(workspace)}-{_safe_token(args.execution_profile)}"


def _effective_build_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.build_id) != DEFAULT_BUILD_ID:
        return str(args.build_id)
    return f"{DEFAULT_BUILD_ID}-{_workspace_token(workspace)}-{_safe_token(args.execution_profile)}"


def _effective_issue_id(args: argparse.Namespace, workspace: Path) -> str:
    return f"{ISSUE_ID}-{_workspace_token(workspace)}-{_safe_token(args.execution_profile)}"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 probe P-01: bare minimum single-issue cards-engine run.")
    parser.add_argument("--workspace", default=".probe_workspace_p01")
    parser.add_argument(
        "--execution-profile",
        default=ARTIFACT_EXECUTION_PROFILE,
        choices=(APP_EXECUTION_PROFILE, ARTIFACT_EXECUTION_PROFILE),
    )
    parser.add_argument("--artifact-path", default=DEFAULT_REQUESTED_ARTIFACT)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--ollama-host", default="")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--build-id", default=DEFAULT_BUILD_ID)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _issue_payload(args: argparse.Namespace, issue_id: str) -> dict[str, Any]:
    artifact_path = str(args.artifact_path)
    execution_profile = str(args.execution_profile)
    artifact_contract = {
        "kind": "app" if execution_profile == APP_EXECUTION_PROFILE else "artifact",
        "primary_output": artifact_path,
        "required_write_paths": [artifact_path],
    }
    if execution_profile == APP_EXECUTION_PROFILE:
        artifact_contract["entrypoint_path"] = artifact_path
    return {
        "id": issue_id,
        "summary": (
            f"Write {artifact_path} containing a Python function fibonacci_sequence(n) "
            "that returns the Fibonacci sequence up to n terms. Then call update_issue_status "
            "with status code_review in the same response."
        ),
        "seat": "coder",
        "priority": 1.0,
        "status": "ready",
        "depends_on": [],
        "params": {
            "execution_profile": execution_profile,
            "artifact_contract": artifact_contract,
        },
    }


def _observed_result(run_status: str) -> str:
    if run_status == "done":
        return "success"
    if run_status == "incomplete":
        return "partial success"
    if run_status in {"failed", "terminal_failure"}:
        return "failure"
    return "partial success"


def _event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in events:
        name = str(row.get("event") or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return counts


def _turn_event_samples(workspace: Path, session_id: str) -> dict[str, list[dict[str, Any]]]:
    records = workspace_log_records(workspace, session_id, event_names={"turn_complete", "turn_failed"})
    samples = {"turn_complete": [], "turn_failed": []}
    for record in records:
        event_name = str(record.get("event") or "").strip()
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        row = {
            "event": event_name,
            "issue_id": str(data.get("issue_id") or ""),
            "role": str(data.get("role") or record.get("role") or ""),
            "turn_index": int(data.get("turn_index") or 0),
            "tool_calls": int(data.get("tool_calls") or 0),
            "duration_ms": int(data.get("duration_ms") or 0),
            "error": str(data.get("error") or ""),
            "type": str(data.get("type") or ""),
        }
        samples.setdefault(event_name, []).append(row)
    return samples


def _written_artifacts(summary: dict[str, Any]) -> list[str]:
    provenance = summary.get("truthful_runtime_artifact_provenance")
    if not isinstance(provenance, dict):
        return []
    rows = provenance.get("artifacts")
    if not isinstance(rows, list):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("artifact_path") or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(str(args.workspace)).resolve()
    session_id = _effective_session_id(args, workspace)
    build_id = _effective_build_id(args, workspace)
    issue_id = _effective_issue_id(args, workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    write_probe_runtime_root(
        workspace,
        epic_id=EPIC_ID,
        environment_model=str(args.model),
        issues=[_issue_payload(args, issue_id)],
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )

    with applied_probe_env(
        provider=str(args.provider),
        ollama_host=str(args.ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        pipeline = ExecutionPipeline(
            workspace=workspace,
            department="core",
            config_root=workspace,
            run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
        )
        pipeline_result = await pipeline.run_card(
            issue_id,
            session_id=session_id,
            build_id=build_id,
        )

    summary = run_summary(workspace, session_id)
    lifecycle_events = protocol_events(workspace, session_id)
    runtime_event_rows = runtime_events(workspace, session_id)
    artifact_hits = collect_artifact_hits(workspace, session_id, ARTIFACT_NAMES)
    turn_samples = _turn_event_samples(workspace, session_id)
    run_status = str(summary.get("status") or "")
    written_artifacts = _written_artifacts(summary)

    return {
        "schema_version": "phase1_probe.p01.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-01",
        "probe_status": "observed",
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": _observed_result(run_status),
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "workspace": str(workspace),
        "session_id": session_id,
        "build_id": build_id,
        "execution_profile": str(args.execution_profile),
        "requested_artifact_path": str(args.artifact_path),
        "run_ledger_backend": "protocol_forced_by_probe",
        "pipeline_result": json_safe(pipeline_result),
        "run_summary": summary,
        "run_summary_execution_profile": summary.get("execution_profile"),
        "run_summary_artifact_contract": summary.get("artifact_contract"),
        "run_summary_stop_reason": summary.get("stop_reason"),
        "run_summary_has_stop_reason": "stop_reason" in summary,
        "artifact_hits": {
            name: {
                "count": len(paths),
                "paths": paths,
            }
            for name, paths in artifact_hits.items()
        },
        "artifact_observation": {
            "requested_paths": [str(args.artifact_path)],
            "requested_paths_present": [str(args.artifact_path)] if (workspace / str(args.artifact_path)).exists() else [],
            "written_paths": written_artifacts,
            "matches_requested": written_artifacts == [str(args.artifact_path)],
        },
        "protocol_events": {
            "count": len(lifecycle_events),
            "kinds": [str(row.get("kind") or "") for row in lifecycle_events],
            "run_finalized_observed": any(str(row.get("kind") or "") == "run_finalized" for row in lifecycle_events),
        },
        "runtime_events": {
            "count": len(runtime_event_rows),
            "event_counts": _event_counts(runtime_event_rows),
            "turn_complete_samples": turn_samples.get("turn_complete", []),
            "turn_failed_samples": turn_samples.get("turn_failed", []),
        },
    }


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": "phase1_probe.p01.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-01",
        "probe_status": "blocked",
        "proof_kind": "live",
        "observed_path": "blocked" if is_environment_blocker(error) else "primary",
        "observed_result": "environment blocker" if is_environment_blocker(error) else "failure",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "workspace": str(Path(str(args.workspace)).resolve()),
        "session_id": str(args.session_id),
        "build_id": str(args.build_id),
        "error_type": type(error).__name__,
        "error": str(error),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    try:
        payload = asyncio.run(_run_probe(args))
    except Exception as exc:  # noqa: BLE001
        payload = _blocked_payload(args, exc)

    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"observed_result={persisted.get('observed_result')}",
                    f"run_status={((persisted.get('run_summary') or {}).get('status') if isinstance(persisted.get('run_summary'), dict) else '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("probe_status") or "") == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
