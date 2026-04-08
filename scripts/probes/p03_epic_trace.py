from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.core.cards_runtime_contract import ARTIFACT_EXECUTION_PROFILE
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.runtime.execution_pipeline import ExecutionPipeline
from scripts.probes.probe_support import (
    applied_probe_env,
    is_environment_blocker,
    json_safe,
    now_utc_iso,
    observability_inventory,
    protocol_events,
    run_summary,
    runtime_events,
    seed_runtime_settings_context,
    simulate_dynamic_priority_order,
    workspace_log_records,
    write_probe_runtime_root,
    write_report,
)

EPIC_ID = "probe-p03-epic-trace"
DEFAULT_SESSION_ID = "probe-p03-epic-trace"
DEFAULT_BUILD_ID = "build-probe-p03-epic-trace"
DEFAULT_OUTPUT = "benchmarks/results/probes/p03_epic_trace.json"
REQUESTED_ARTIFACTS = {
    "P03-SCHEMA": "agent_output/schema.json",
    "P03-WRITER": "agent_output/writer.py",
    "P03-READER": "agent_output/reader.py",
}


def _safe_token(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()).strip("-") or "probe"


def _effective_session_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.session_id) != DEFAULT_SESSION_ID:
        return str(args.session_id)
    return f"{DEFAULT_SESSION_ID}-{_safe_token(workspace.name)}-{_safe_token(args.execution_profile)}"


def _effective_build_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.build_id) != DEFAULT_BUILD_ID:
        return str(args.build_id)
    return f"{DEFAULT_BUILD_ID}-{_safe_token(workspace.name)}-{_safe_token(args.execution_profile)}"


def _issue_id_map(args: argparse.Namespace, workspace: Path) -> dict[str, str]:
    suffix = f"{_safe_token(workspace.name)}-{_safe_token(args.execution_profile)}"
    return {base_id: f"{base_id}-{suffix}" for base_id in REQUESTED_ARTIFACTS}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 probe P-03: cards-engine multi-issue pipeline trace.")
    parser.add_argument("--workspace", default=".probe_workspace_p03")
    parser.add_argument(
        "--execution-profile",
        default=ARTIFACT_EXECUTION_PROFILE,
        choices=(ARTIFACT_EXECUTION_PROFILE,),
    )
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


def _issues(execution_profile: str, issue_ids: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "id": issue_ids["P03-SCHEMA"],
            "summary": (
                "Write agent_output/schema.json describing a task record with id, title, and status fields. "
                "Then call update_issue_status with status code_review in the same response."
            ),
            "seat": "coder",
            "priority": 1.0,
            "status": "ready",
            "depends_on": [],
            "params": {
                "execution_profile": execution_profile,
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": REQUESTED_ARTIFACTS["P03-SCHEMA"],
                    "required_write_paths": [REQUESTED_ARTIFACTS["P03-SCHEMA"]],
                },
            },
        },
        {
            "id": issue_ids["P03-WRITER"],
            "summary": (
                "After the schema exists, write agent_output/writer.py with a Python function append_task(path, task) "
                "that appends a task to a JSON list. Then call update_issue_status with status code_review."
            ),
            "seat": "coder",
            "priority": 2.0,
            "status": "ready",
            "depends_on": [issue_ids["P03-SCHEMA"]],
            "params": {
                "execution_profile": execution_profile,
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": REQUESTED_ARTIFACTS["P03-WRITER"],
                    "required_write_paths": [REQUESTED_ARTIFACTS["P03-WRITER"]],
                    "required_read_paths": [REQUESTED_ARTIFACTS["P03-SCHEMA"]],
                },
            },
        },
        {
            "id": issue_ids["P03-READER"],
            "summary": (
                "After the schema exists, write agent_output/reader.py with a Python function list_tasks(path) "
                "that returns a parsed JSON list. Then call update_issue_status with status code_review."
            ),
            "seat": "coder",
            "priority": 2.0,
            "status": "ready",
            "depends_on": [issue_ids["P03-SCHEMA"]],
            "params": {
                "execution_profile": execution_profile,
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": REQUESTED_ARTIFACTS["P03-READER"],
                    "required_write_paths": [REQUESTED_ARTIFACTS["P03-READER"]],
                    "required_read_paths": [REQUESTED_ARTIFACTS["P03-SCHEMA"]],
                },
            },
        },
    ]


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
        event_name = str(row.get("event") or "").strip()
        if not event_name:
            continue
        counts[event_name] = counts.get(event_name, 0) + 1
    return counts


def _issue_order(runtime_event_rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for event_name in ("turn_complete", "turn_start", "turn_failed"):
        for row in runtime_event_rows:
            if str(row.get("event") or "").strip() != event_name:
                continue
            issue_id = str(row.get("issue_id") or "").strip()
            if not issue_id or issue_id in seen:
                continue
            seen.add(issue_id)
            ordered.append(issue_id)
        if ordered:
            break
    return ordered


def _log_event_samples(workspace: Path, session_id: str) -> dict[str, list[dict[str, Any]]]:
    records = workspace_log_records(workspace, session_id, event_names={"turn_complete", "turn_failed"})
    payload = {"turn_complete": [], "turn_failed": []}
    for record in records:
        event_name = str(record.get("event") or "").strip()
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        payload.setdefault(event_name, []).append(
            {
                "issue_id": str(data.get("issue_id") or ""),
                "role": str(data.get("role") or record.get("role") or ""),
                "turn_index": int(data.get("turn_index") or 0),
                "tool_calls": int(data.get("tool_calls") or 0),
                "duration_ms": int(data.get("duration_ms") or 0),
                "tokens": data.get("tokens"),
                "error": str(data.get("error") or ""),
                "type": str(data.get("type") or ""),
            }
        )
    return payload


def _contract_event_samples(workspace: Path, session_id: str) -> dict[str, list[dict[str, Any]]]:
    records = workspace_log_records(workspace, session_id, event_names={"turn_corrective_reprompt", "turn_non_progress"})
    payload = {"turn_corrective_reprompt": [], "turn_non_progress": []}
    for record in records:
        event_name = str(record.get("event") or "").strip()
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        payload.setdefault(event_name, []).append(
            {
                "issue_id": str(data.get("issue_id") or ""),
                "role": str(data.get("role") or record.get("role") or ""),
                "turn_index": int(data.get("turn_index") or 0),
                "reason": str(data.get("reason") or ""),
                "contract_reasons": list(data.get("contract_reasons") or []),
            }
        )
    return payload


def _policy_violation_reports(workspace: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted((workspace / "agent_output").glob("policy_violation_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            reports.append(payload)
    return reports


def _requested_artifact_rows(workspace: Path, issue_ids: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for base_id, relative_path in REQUESTED_ARTIFACTS.items():
        rows.append(
            {
                "issue_id": issue_ids[base_id],
                "path": relative_path,
                "present": (workspace / relative_path).exists(),
            }
        )
    return rows


def _build_payload(
    *,
    args: argparse.Namespace,
    workspace: Path,
    session_id: str,
    build_id: str,
    issue_rows: list[Any],
    summary: dict[str, Any],
    lifecycle_events: list[dict[str, Any]],
    runtime_event_rows: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    pipeline_result: Any,
    run_error: Exception | None,
    issue_ids: dict[str, str],
) -> dict[str, Any]:
    turn_samples = _log_event_samples(workspace, session_id)
    contract_samples = _contract_event_samples(workspace, session_id)
    actual_order = _issue_order(runtime_event_rows)
    expected_order = simulate_dynamic_priority_order(_issues(str(args.execution_profile), issue_ids))
    run_status = str(summary.get("status") or "")
    payload = {
        "schema_version": "phase1_probe.p03.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-03",
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
        "run_ledger_backend": "protocol_forced_by_probe",
        "pipeline_result": json_safe(pipeline_result),
        "run_summary": summary,
        "issue_statuses": [
            {
                "id": str(getattr(issue, "id", "")),
                "status": getattr(getattr(issue, "status", None), "value", getattr(issue, "status", None)),
            }
            for issue in issue_rows
        ],
        "execution_order": {
            "expected_dynamic_priority_order": expected_order,
            "observed_issue_order": actual_order,
            "matches": actual_order == expected_order,
        },
        "requested_artifacts": _requested_artifact_rows(workspace, issue_ids),
        "policy_violations": _policy_violation_reports(workspace),
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
            "turn_corrective_reprompt_samples": contract_samples.get("turn_corrective_reprompt", []),
            "turn_non_progress_samples": contract_samples.get("turn_non_progress", []),
        },
        "observability_inventory": inventory,
    }
    if run_error is not None:
        payload["error_type"] = type(run_error).__name__
        payload["error"] = str(run_error)
    return payload


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(str(args.workspace)).resolve()
    session_id = _effective_session_id(args, workspace)
    build_id = _effective_build_id(args, workspace)
    issue_ids = _issue_id_map(args, workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    issues = _issues(str(args.execution_profile), issue_ids)
    write_probe_runtime_root(
        workspace,
        epic_id=EPIC_ID,
        environment_model=str(args.model),
        issues=issues,
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
    )

    pipeline_result: Any = None
    issue_rows: list[Any] = []
    run_error: Exception | None = None
    with applied_probe_env(
        provider=str(args.provider),
        ollama_host=str(args.ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        await seed_runtime_settings_context()
        pipeline = ExecutionPipeline(
            workspace=workspace,
            department="core",
            config_root=workspace,
            run_ledger_repo=AsyncProtocolRunLedgerRepository(workspace),
        )
        try:
            pipeline_result = await pipeline.run_card(
                EPIC_ID,
                session_id=session_id,
                build_id=build_id,
            )
        except Exception as exc:  # noqa: BLE001
            run_error = exc
            if is_environment_blocker(exc):
                raise
        try:
            issue_rows = await pipeline.async_cards.get_by_build(build_id)
        except Exception:  # noqa: BLE001
            issue_rows = []

    summary = run_summary(workspace, session_id)
    lifecycle_events = protocol_events(workspace, session_id)
    runtime_event_rows = runtime_events(workspace, session_id)
    inventory = observability_inventory(workspace, session_id)
    return _build_payload(
        args=args,
        workspace=workspace,
        session_id=session_id,
        build_id=build_id,
        issue_rows=issue_rows,
        summary=summary,
        lifecycle_events=lifecycle_events,
        runtime_event_rows=runtime_event_rows,
        inventory=inventory,
        pipeline_result=pipeline_result,
        run_error=run_error,
        issue_ids=issue_ids,
    )


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": "phase1_probe.p03.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-03",
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
