from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, cast

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.governed_agent_broker_service import GovernedAgentHostBroker
from orket.application.services.governed_agent_fixture import SecondIterationDeterministicVerifier
from orket.application.services.governed_agent_inspection_service import (
    GovernedAgentInspectionService,
)
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.application.services.governed_agent_operator_service import GovernedAgentOperatorService
from orket.core.contracts import WorkloadRecord
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import GovernedAgentWorkloadLaunch
from orket.interfaces.governed_agent_provider_selection import (
    GovernedAgentProviderSelection,
    model_map_for_roles,
    select_governed_agent_provider,
)
from orket_extension_sdk import AgentIterationRequest, canonical_digest_sha256


def add_governed_agent_subparser(subparsers: Any) -> None:
    parser = subparsers.add_parser("agent", help="Submit, inspect, replay, or cancel a governed agent run.")
    commands = parser.add_subparsers(dest="agent_command", required=True)
    for command in ("inspect", "replay"):
        child = commands.add_parser(command, help=f"{command.title()} durable governed-agent state.")
        child.add_argument("run_id")
        child.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
        child.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    cancel = commands.add_parser("cancel", help="Publish an operator cancellation for a governed agent run.")
    cancel.add_argument("run_id")
    cancel.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
    cancel.add_argument("--action-id", required=True)
    cancel.add_argument("--actor-ref", required=True)
    cancel.add_argument("--timestamp-utc", required=True)
    cancel.add_argument("--reason", required=True)
    cancel.add_argument("--cancellation-epoch", required=True, type=int)
    cancel.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    submit = commands.add_parser("submit", help="Run a bounded governed-agent workload.")
    submit.add_argument("workload_id")
    submit.add_argument("--db", required=True, help="Governed control-plane SQLite path.")
    submit.add_argument("--catalog", required=True, help="Extension catalog containing the agent workload.")
    submit.add_argument("--request", required=True, help="Validated initial iteration request JSON.")
    submit.add_argument("--creation-timestamp-utc", required=True)
    submit.add_argument("--decision-timestamp-utc", action="append", required=True)
    submit.add_argument("--next-lease-expires-at-utc", action="append", default=[])
    provider = submit.add_mutually_exclusive_group(required=True)
    provider.add_argument("--deterministic-fixture", action="store_true")
    provider.add_argument("--ollama-model", help="Exact installed Ollama model for every role by default.")
    for role in ("planner", "actor", "critic"):
        submit.add_argument(f"--{role}-model", help=f"Exact installed Ollama model override for {role}.")
    submit.add_argument("--ollama-base-url", default="", help="Optional Ollama base URL override.")
    submit.add_argument("--inventory-timeout-seconds", type=float, default=30.0)
    submit.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")


def handle_governed_agent_command(args: argparse.Namespace) -> int:
    try:
        db_path = Path(str(args.db)).resolve()
        project_root = Path.cwd().resolve()
        catalog_path = Path(str(args.catalog)).resolve() if hasattr(args, "catalog") else None
        request_path = Path(str(args.request)).resolve() if hasattr(args, "request") else None
        result = asyncio.run(_run_command(args, db_path, project_root, catalog_path, request_path))
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
    if bool(getattr(args, "json", False)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif result.get("ok"):
        print(_render_human(result))
    else:
        print(f"FAIL: {result.get('error', 'unknown governed-agent error')}")
    return 0 if result.get("ok") else 1


async def _run_command(
    args: argparse.Namespace,
    db_path: Path,
    project_root: Path,
    catalog_path: Path | None,
    request_path: Path | None,
) -> dict[str, Any]:
    execution = AsyncControlPlaneExecutionRepository(db_path)
    iterations = AsyncGovernedAgentRepository(db_path)
    records = AsyncControlPlaneRecordRepository(db_path)
    command = str(args.agent_command)
    if command == "submit":
        return await _submit(
            args=args,
            db_path=db_path,
            project_root=project_root,
            catalog_path=catalog_path,
            request_path=request_path,
            execution=execution,
            iterations=iterations,
            records=records,
        )
    if command in {"inspect", "replay"}:
        inspector = GovernedAgentInspectionService(
            execution_repository=execution,
            iteration_repository=iterations,
            call_repository=iterations,
            truth_repository=records,
        )
        payload = (
            await inspector.inspect(run_id=str(args.run_id))
            if command == "inspect"
            else await inspector.replay(run_id=str(args.run_id))
        )
        if payload is None:
            raise ValueError("E_AGENT_RUN_NOT_FOUND")
        matched = command != "replay" or payload["status"] == "matched"
        return {"ok": matched, **payload}
    operator = GovernedAgentOperatorService(
        execution_repository=execution,
        iteration_repository=iterations,
        operator_repository=records,
        truth_repository=records,
        invoker=_NoActiveProcessInvoker(),
    )
    cancelled = await operator.cancel_run(
        run_id=str(args.run_id),
        action_id=str(args.action_id),
        actor_ref=str(args.actor_ref),
        timestamp_utc=str(args.timestamp_utc),
        reason=str(args.reason),
        cancellation_epoch=int(args.cancellation_epoch),
        grace_period_seconds=0,
    )
    return {
        "ok": True,
        "object_type": "governed_agent_cancellation_result",
        "run": cancelled.run.model_dump(mode="json"),
        "operator_action": cancelled.action.model_dump(mode="json"),
        "final_truth": cancelled.final_truth.model_dump(mode="json"),
        "child_confirmed_stopped": cancelled.child_confirmed_stopped,
    }


async def _submit(
    *,
    args: argparse.Namespace,
    db_path: Path,
    project_root: Path,
    catalog_path: Path | None,
    request_path: Path | None,
    execution: AsyncControlPlaneExecutionRepository,
    iterations: AsyncGovernedAgentRepository,
    records: AsyncControlPlaneRecordRepository,
) -> dict[str, Any]:
    if catalog_path is None or request_path is None:
        raise ValueError("E_AGENT_SUBMIT_PATHS_REQUIRED")
    launch = await asyncio.to_thread(
        _resolve_launch,
        catalog_path,
        project_root,
        str(args.workload_id),
    )
    request_payload = await asyncio.to_thread(_read_json_object, request_path)
    request = AgentIterationRequest.from_wire(request_payload)
    selection = await _select_provider(args, request, launch)
    service = _build_loop_service(execution, iterations, records, launch, selection)
    try:
        execution_result = await service.run_bounded(
            initial_request_payload=request_payload,
            workload_record=WorkloadRecord.model_validate(launch.control_plane_workload_record),
            extension_digest=launch.extension_digest,
            configuration_digest=_configuration_digest(launch, selection.configuration_payload()),
            admission_receipt_ref=f"agent-catalog-admission:{launch.extension_id}:{launch.workload_id}",
            creation_timestamp_utc=str(args.creation_timestamp_utc),
            decision_timestamps_utc=tuple(args.decision_timestamp_utc),
            next_lease_expiries_utc=tuple(args.next_lease_expires_at_utc),
        )
    finally:
        await selection.close()
    inspector = GovernedAgentInspectionService(
        execution_repository=execution,
        iteration_repository=iterations,
        call_repository=iterations,
        truth_repository=records,
    )
    inspection = await inspector.inspect(run_id=request.identity.run_id)
    return _execution_payload(execution_result, selection, inspection, db_path)


async def _select_provider(
    args: argparse.Namespace,
    request: AgentIterationRequest,
    launch: GovernedAgentWorkloadLaunch,
) -> GovernedAgentProviderSelection:
    models = (
        {}
        if bool(args.deterministic_fixture)
        else model_map_for_roles(
            request,
            default_model=str(getattr(args, "ollama_model", "") or ""),
            role_overrides={
                role: str(getattr(args, f"{role}_model", "") or "")
                for role in ("planner", "actor", "critic")
            },
        )
    )
    return await select_governed_agent_provider(
        request=request,
        launch=launch,
        deterministic_fixture=bool(args.deterministic_fixture),
        model_by_role=models,
        ollama_base_url=str(args.ollama_base_url or ""),
        inventory_timeout_seconds=float(args.inventory_timeout_seconds),
    )


def _build_loop_service(
    execution: AsyncControlPlaneExecutionRepository,
    iterations: AsyncGovernedAgentRepository,
    records: AsyncControlPlaneRecordRepository,
    launch: GovernedAgentWorkloadLaunch,
    selection: GovernedAgentProviderSelection,
) -> GovernedAgentLoopService:
    broker = GovernedAgentHostBroker(
        iteration_repository=iterations,
        call_repository=iterations,
        model_provider=selection.provider,
        model_profiles=selection.profiles,
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=launch.extension_root,
        entrypoint=launch.entrypoint,
        allowed_stdlib_modules=launch.allowed_stdlib_modules,
        broker=broker,
    )
    return GovernedAgentLoopService(
        execution_repository=execution,
        iteration_repository=iterations,
        truth_repository=records,
        invoker=invoker,
        verifier=SecondIterationDeterministicVerifier(),
    )


def _execution_payload(execution_result, selection, inspection, db_path: Path) -> dict[str, Any]:
    return {
        "ok": execution_result.final_truth is not None,
        "object_type": "governed_agent_execution",
        "proof_posture": selection.proof_posture,
        "observed_path": selection.observed_path,
        "observed_result": "success" if execution_result.final_truth is not None else "failure",
        "model_targets": selection.targets,
        "db_path": str(db_path),
        "run": execution_result.run.model_dump(mode="json"),
        "decisions": [decision.to_payload() for decision in execution_result.decisions],
        "final_truth": (
            None if execution_result.final_truth is None else execution_result.final_truth.model_dump(mode="json")
        ),
        "normalized_reason": execution_result.normalized_reason,
        "iterations": [] if inspection is None else inspection["iterations"],
    }


def _resolve_launch(
    catalog_path: Path,
    project_root: Path,
    workload_id: str,
) -> GovernedAgentWorkloadLaunch:
    manager = ExtensionManager(catalog_path=catalog_path, project_root=project_root)
    return manager.resolve_governed_agent_workload(workload_id)


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("E_AGENT_REQUEST_OBJECT_REQUIRED")
    return payload


def _configuration_digest(launch: GovernedAgentWorkloadLaunch, provider: dict[str, Any]) -> str:
    return "sha256:" + cast(
        str,
        canonical_digest_sha256(
            {
                "extension_id": launch.extension_id,
                "extension_version": launch.extension_version,
                "manifest_digest_sha256": launch.manifest_digest_sha256,
                "agent_declaration": launch.agent_declaration,
                "provider": provider,
            }
        ),
    )


class _NoActiveProcessInvoker:
    async def invoke_once(self, **_: Any) -> Any:
        raise RuntimeError("E_AGENT_CLI_INVOKER_NOT_CONFIGURED")

    async def cancel_and_reap(self, **_: Any) -> bool:
        return True


def _render_human(result: dict[str, Any]) -> str:
    object_type = str(result.get("object_type") or "")
    if object_type == "governed_agent_replay":
        return f"agent replay: run={result['run_id']} status={result['status']}"
    run = result.get("run")
    if isinstance(run, dict):
        return f"agent {object_type}: run={run.get('run_id')} state={run.get('lifecycle_state')}"
    return f"agent {object_type}: ok"
