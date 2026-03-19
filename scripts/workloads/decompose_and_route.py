#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.core.cards_runtime_contract import ARTIFACT_EXECUTION_PROFILE
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
    write_probe_runtime_root,
    write_report,
)
from scripts.workloads.workload_support import (
    artifact_inventory,
    display_path,
    load_json_object,
    load_python_symbols,
    run_strict_json_model,
    validate_json_contract,
    write_json,
)

DEFAULT_OUTPUT = "benchmarks/results/workloads/decompose_and_route.json"
DEFAULT_FIXTURE = "scripts/workloads/fixtures/decompose_and_route_v1/task_spec.json"
DEFAULT_WORKSPACE = "workspace/default"
DEFAULT_SESSION_ID = "workload-s06-decompose-and-route"
DEFAULT_BUILD_ID = "build-workload-s06-decompose-and-route"
EPIC_ID = "workload-s06-decompose-and-route"


class _SubtaskContract(BaseModel):
    task_id: str
    summary: str
    artifact_path: str
    depends_on: list[str] = Field(default_factory=list)

    @field_validator("depends_on", mode="before")
    @classmethod
    def _normalize_depends_on(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            candidate = value.strip()
            return [candidate] if candidate else []
        if isinstance(value, (list, tuple)):
            return [candidate for item in value if (candidate := str(item or "").strip())]
        raise TypeError("depends_on must be a list, string, or null")


class _DecompositionContract(BaseModel):
    summary: str
    subtasks: list[_SubtaskContract] = Field(default_factory=list)


_DecompositionContract.model_rebuild()


def _safe_token(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()).strip("-") or "probe"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 workload S-06: direct decomposition plus cards routing.")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
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


def _effective_session_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.session_id) != DEFAULT_SESSION_ID:
        return str(args.session_id)
    return f"{DEFAULT_SESSION_ID}-{_safe_token(workspace.name)}"


def _effective_build_id(args: argparse.Namespace, workspace: Path) -> str:
    if str(args.build_id) != DEFAULT_BUILD_ID:
        return str(args.build_id)
    return f"{DEFAULT_BUILD_ID}-{_safe_token(workspace.name)}"


def _build_decomposition_messages(spec: dict[str, Any]) -> list[dict[str, str]]:
    allowed_paths = [str(row.get("path") or "") for row in list(spec.get("artifacts") or []) if isinstance(row, dict)]
    return [
        {
            "role": "system",
            "content": (
                "Return exactly one JSON object with keys summary and subtasks. "
                "Each subtask must contain task_id, summary, artifact_path, depends_on. "
                "Use exactly one subtask per approved artifact path. "
                "Do not invent new artifact paths. Do not use markdown fences."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Task summary: {spec.get('task_summary')}\n"
                f"Task description: {spec.get('task_description')}\n"
                f"Approved artifact paths: {json.dumps(allowed_paths)}\n"
                "Decompose the task into the smallest useful ordered subtasks."
            ),
        },
    ]


def _validate_decomposition_plan(plan: dict[str, Any], spec: dict[str, Any]) -> tuple[dict[str, Any], bool, list[str]]:
    errors: list[str] = []
    subtasks = [dict(row) for row in list(plan.get("subtasks") or []) if isinstance(row, dict)]
    allowed = {str(row.get("path") or "") for row in list(spec.get("artifacts") or []) if isinstance(row, dict)}
    ids = [str(row.get("task_id") or "").strip() for row in subtasks]
    paths = [str(row.get("artifact_path") or "").strip() for row in subtasks]
    if len(subtasks) != len(allowed):
        errors.append("subtask_count_mismatch")
    if any(not item for item in ids):
        errors.append("task_id_missing")
    if len(set(ids)) != len(ids):
        errors.append("task_id_not_unique")
    if set(paths) != allowed:
        errors.append("artifact_coverage_mismatch")
    id_set = set(ids)
    for row in subtasks:
        for dep in [str(item or "").strip() for item in list(row.get("depends_on") or [])]:
            if dep not in id_set:
                errors.append(f"unknown_dependency:{dep}")
    return {"summary": str(plan.get("summary") or ""), "subtasks": subtasks}, not errors, errors


def _build_issues(plan: dict[str, Any], spec: dict[str, Any], workspace: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    artifact_map = {
        str(row.get("path") or ""): dict(row)
        for row in list(spec.get("artifacts") or [])
        if isinstance(row, dict) and str(row.get("path") or "").strip()
    }
    issue_id_map: dict[str, str] = {}
    for row in list(plan.get("subtasks") or []):
        task_id = str(row.get("task_id") or "").strip()
        issue_id_map[task_id] = f"{task_id}-{_safe_token(workspace.name)}"

    issues: list[dict[str, Any]] = []
    for index, row in enumerate(list(plan.get("subtasks") or []), start=1):
        artifact_path = str(row.get("artifact_path") or "").strip()
        artifact_spec = artifact_map[artifact_path]
        task_id = str(row.get("task_id") or "").strip()
        issues.append(
            {
                "id": issue_id_map[task_id],
                "summary": (
                    f"{str(row.get('summary') or '').strip()}. "
                    f"{str(artifact_spec.get('issue_hint') or '').strip()} "
                    "Then call update_issue_status with status code_review in the same response."
                ),
                "seat": "coder",
                "priority": float(index),
                "status": "ready",
                "depends_on": [issue_id_map[str(dep)] for dep in list(row.get("depends_on") or [])],
                "params": {
                    "execution_profile": ARTIFACT_EXECUTION_PROFILE,
                    "artifact_contract": {
                        "kind": str(artifact_spec.get("kind") or "artifact"),
                        "primary_output": artifact_path,
                        "required_write_paths": [artifact_path],
                        "required_read_paths": list(artifact_spec.get("required_read_paths") or []),
                    },
                },
            }
        )
    return issues, issue_id_map


def _execution_order(runtime_rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in runtime_rows:
        issue_id = str(row.get("issue_id") or "").strip()
        if not issue_id or issue_id in seen:
            continue
        seen.add(issue_id)
        ordered.append(issue_id)
    return ordered


def _verify_round_trip(*, workspace: Path, spec: dict[str, Any]) -> dict[str, Any]:
    schema_path = workspace / "agent_output/schema.json"
    writer_path = workspace / "agent_output/writer.py"
    reader_path = workspace / "agent_output/reader.py"
    sample_path = workspace / "agent_output/sample_tasks.json"
    result: dict[str, Any] = {
        "schema_present": schema_path.exists(),
        "writer_present": writer_path.exists(),
        "reader_present": reader_path.exists(),
        "schema_valid": False,
        "writer_loaded": False,
        "reader_loaded": False,
        "round_trip_success": False,
    }
    try:
        schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
        result["schema_valid"] = isinstance(schema_payload, dict)
    except Exception as exc:  # noqa: BLE001
        result["schema_error"] = f"{type(exc).__name__}:{exc}"
    try:
        writer_symbols = load_python_symbols(writer_path)
        writer = writer_symbols.get("append_task")
        result["writer_loaded"] = callable(writer)
    except Exception as exc:  # noqa: BLE001
        result["writer_error"] = f"{type(exc).__name__}:{exc}"
        writer = None
    try:
        reader_symbols = load_python_symbols(reader_path)
        reader = reader_symbols.get("list_tasks")
        result["reader_loaded"] = callable(reader)
    except Exception as exc:  # noqa: BLE001
        result["reader_error"] = f"{type(exc).__name__}:{exc}"
        reader = None
    if callable(writer) and callable(reader):
        sample_path.write_text("[]\n", encoding="utf-8")
        sample_task = dict(spec.get("sample_task") or {})
        try:
            writer(str(sample_path), sample_task)
            loaded = reader(str(sample_path))
            result["round_trip_success"] = isinstance(loaded, list) and bool(loaded) and loaded[0] == sample_task
            result["loaded_value"] = loaded
        except Exception as exc:  # noqa: BLE001
            result["round_trip_error"] = f"{type(exc).__name__}:{exc}"
    return result


def _observed_result(*, plan_valid: bool, run_status: str, round_trip: dict[str, Any]) -> str:
    if plan_valid and run_status == "done" and bool(round_trip.get("round_trip_success")):
        return "success"
    if plan_valid and (
        bool(round_trip.get("schema_present")) or bool(round_trip.get("writer_present")) or bool(round_trip.get("reader_present"))
    ):
        return "partial success"
    return "failure"


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(str(args.workspace)).resolve()
    fixture_path = Path(str(args.fixture)).resolve()
    if not fixture_path.is_file():
        raise FileNotFoundError(f"fixture_not_found:{fixture_path}")
    spec = load_json_object(fixture_path)
    session_id = _effective_session_id(args, workspace)
    build_id = _effective_build_id(args, workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    plan_text, plan_raw = await run_strict_json_model(
        model=str(args.model),
        provider=str(args.provider),
        ollama_host=str(args.ollama_host),
        temperature=float(args.temperature),
        seed=int(args.seed),
        timeout=int(args.timeout),
        messages=_build_decomposition_messages(spec),
        runtime_context={"workload_id": "S-06", "fixture_id": str(spec.get("fixture_id") or "")},
    )
    plan_payload, response_json_found, contract_valid, advisory_errors = validate_json_contract(
        text=plan_text,
        model_cls=_DecompositionContract,
    )
    normalized_plan, plan_valid, plan_errors = _validate_decomposition_plan(plan_payload, spec)

    issues: list[dict[str, Any]] = []
    issue_id_map: dict[str, str] = {}
    pipeline_result: Any = None
    if plan_valid:
        issues, issue_id_map = _build_issues(normalized_plan, spec, workspace)
        write_probe_runtime_root(
            workspace,
            epic_id=EPIC_ID,
            environment_model=str(args.model),
            issues=issues,
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
            pipeline_result = await pipeline.run_epic(EPIC_ID, session_id=session_id, build_id=build_id)

    summary = run_summary(workspace, session_id)
    runtime_rows = runtime_events(workspace, session_id)
    round_trip = _verify_round_trip(workspace=workspace, spec=spec) if plan_valid else {
        "schema_present": False,
        "writer_present": False,
        "reader_present": False,
        "round_trip_success": False,
    }

    artifact_dir = workspace / "workloads" / "s06_decompose_and_route" / build_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_json(artifact_dir / "task_spec.json", spec)
    write_json(artifact_dir / "decomposition_plan.json", normalized_plan)
    write_json(artifact_dir / "decomposition_plan_raw.json", plan_raw)
    write_json(artifact_dir / "decomposition_validation.json", {"plan_valid": plan_valid, "plan_errors": plan_errors})
    write_json(artifact_dir / "cards_run_summary.json", summary)
    write_json(artifact_dir / "cards_pipeline_result.json", json_safe(pipeline_result))
    write_json(artifact_dir / "integration_round_trip.json", round_trip)
    (artifact_dir / "decomposition_response.txt").write_text(plan_text, encoding="utf-8")

    observed_result = _observed_result(
        plan_valid=plan_valid,
        run_status=str(summary.get("status") or ""),
        round_trip=round_trip,
    )
    return {
        "schema_version": "workloads.s06_decompose_and_route.v1",
        "recorded_at_utc": now_utc_iso(),
        "workload_id": "S-06",
        "probe_status": "observed",
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": observed_result,
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "workspace": str(workspace),
        "session_id": session_id,
        "build_id": build_id,
        "decomposition_mode": "direct_model_v1",
        "odr_used": False,
        "fixture": {
            "fixture_id": str(spec.get("fixture_id") or ""),
            "fixture_path": display_path(fixture_path),
        },
        "decomposition_contract": {
            "response_json_found": response_json_found,
            "contract_valid": contract_valid,
            "advisory_errors": advisory_errors,
            "plan_valid": plan_valid,
            "plan_errors": plan_errors,
            "summary": str(normalized_plan.get("summary") or ""),
            "subtasks": list(normalized_plan.get("subtasks") or []),
        },
        "run_summary": summary,
        "execution_order": {
            "planned_issue_ids": [row["id"] for row in issues],
            "observed_issue_ids": _execution_order(runtime_rows),
            "issue_id_map": issue_id_map,
        },
        "protocol_events": {"count": len(protocol_events(workspace, session_id))},
        "runtime_events": {"count": len(runtime_rows)},
        "observability_inventory": observability_inventory(workspace, session_id),
        "integration_round_trip": round_trip,
        "artifact_bundle": {
            "path": artifact_dir.as_posix(),
            "files": artifact_inventory(artifact_dir),
        },
    }


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    blocked = is_environment_blocker(error)
    return {
        "schema_version": "workloads.s06_decompose_and_route.v1",
        "recorded_at_utc": now_utc_iso(),
        "workload_id": "S-06",
        "probe_status": "blocked",
        "proof_kind": "live",
        "observed_path": "blocked" if blocked else "primary",
        "observed_result": "environment blocker" if blocked else "failure",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
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
        round_trip = persisted.get("integration_round_trip") if isinstance(persisted.get("integration_round_trip"), dict) else {}
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"observed_result={persisted.get('observed_result')}",
                    f"round_trip={round_trip.get('round_trip_success', '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("probe_status") or "") == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
