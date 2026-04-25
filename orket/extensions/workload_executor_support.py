from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.application.services.extension_workload_control_plane_service import (
    ExtensionWorkloadControlPlaneService,
    ExtensionWorkloadControlPlaneStart,
)
from orket.core.domain import AuthoritySourceClass, ResultClass
from orket.streaming.contracts import CommitIntent, StreamEventType

from .contracts import RunPlan
from .governed_identity import (
    EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT,
    build_extension_control_bundle,
    build_extension_policy_payload,
    build_governed_identity as build_runtime_governed_identity,
    digest_prefixed,
)
from .models import ExtensionRecord, _ExtensionManifestEntry
from .runtime import ExtensionEngineAdapter, RunContext
from .sdk_workload_runner import SdkSubprocessRunError
from .workload_artifacts import WorkloadArtifacts


def compile_workload(workload: Any, input_config: dict[str, Any], interaction_context: Any | None) -> RunPlan:
    compile_input = dict(input_config)
    compile_fn = workload.compile
    compile_sig = inspect.signature(compile_fn)
    if "interaction_context" in compile_sig.parameters:
        run_plan = compile_fn(compile_input, interaction_context=interaction_context)
    elif len(compile_sig.parameters) >= 2:
        run_plan = compile_fn(compile_input, interaction_context)
    else:
        run_plan = compile_fn(compile_input)
    if not isinstance(run_plan, RunPlan):
        raise TypeError("compile(input_config) must return RunPlan")
    return run_plan


async def execute_plan_actions(
    *,
    run_plan: RunPlan,
    workspace: Path,
    department: str,
    interaction_context: Any | None,
) -> dict[str, Any]:
    action_results: list[dict[str, Any]] = []
    if interaction_context is not None:
        await emit_default_model_events(interaction_context, sdk=False)
    if run_plan.actions:
        adapter = ExtensionEngineAdapter(RunContext(workspace=workspace, department=department))
        for action in run_plan.actions:
            action_results.append(await adapter.execute_action(action))
    return {"plan_hash": run_plan.plan_hash(), "action_count": len(run_plan.actions), "action_results": action_results}


async def emit_default_model_events(interaction_context: Any, *, sdk: bool) -> None:
    model_id = "extension-sdk-v0" if sdk else "extension-default"
    reason = "sdk_workload_run" if sdk else "workload_compile"
    await interaction_context.emit_event(
        StreamEventType.MODEL_SELECTED,
        {"model_id": model_id, "reason": reason, "authoritative": False},
    )
    await interaction_context.emit_event(
        StreamEventType.MODEL_LOADING,
        {"cold_start": False, "progress": 1.0, "authoritative": False},
    )
    await interaction_context.emit_event(
        StreamEventType.MODEL_READY,
        {"model_id": model_id, "warm_state": "warm", "load_ms": 0, "authoritative": False},
    )


def build_sdk_context(
    extension: ExtensionRecord,
    workload: _ExtensionManifestEntry,
    input_config: dict[str, Any],
    workspace: Path,
    artifact_root: Path,
    capability_registry: Any,
    run_id: str,
) -> Any:
    from orket_extension_sdk.workload import WorkloadContext as SDKWorkloadContext

    return SDKWorkloadContext(
        extension_id=extension.extension_id,
        workload_id=workload.workload_id,
        run_id=run_id,
        workspace_root=workspace,
        input_dir=workspace,
        output_dir=artifact_root,
        capabilities=capability_registry,
        seed=int(input_config.get("seed", 0) or 0),
        config=dict(input_config),
    )


def build_governed_identity(
    *,
    artifacts: WorkloadArtifacts,
    extension: ExtensionRecord,
    workload_id: str,
    workload_version: str,
    workload_entrypoint: str,
    required_capabilities: list[str],
    contract_style: str,
    department: str,
    input_identity: str,
) -> dict[str, Any]:
    policy_payload = build_extension_policy_payload(
        contract_style=contract_style,
        security_mode=extension.security_mode,
        security_profile=extension.security_profile,
        security_policy_version=extension.security_policy_version,
        reliable_mode_enabled=artifacts.reproducibility.reliable_mode_enabled(),
        reliable_require_clean_git=artifacts.reliable_require_clean_git_enabled(),
        provenance_verbose_enabled=artifacts.provenance_verbose_enabled(),
        artifact_file_size_cap_bytes=artifacts.artifact_file_size_cap_bytes(),
        artifact_total_size_cap_bytes=artifacts.artifact_total_size_cap_bytes(),
    )
    control_bundle = build_extension_control_bundle(
        extension_id=extension.extension_id,
        extension_version=extension.extension_version,
        source_ref=extension.source_ref,
        resolved_commit_sha=extension.resolved_commit_sha,
        manifest_digest_sha256=extension.manifest_digest_sha256,
        workload_id=workload_id,
        workload_version=workload_version,
        workload_entrypoint=workload_entrypoint,
        required_capabilities=required_capabilities,
        contract_style=contract_style,
        department=department,
        input_identity=input_identity,
        security_mode=extension.security_mode,
        security_profile=extension.security_profile,
        security_policy_version=extension.security_policy_version,
        reliable_mode_enabled=artifacts.reproducibility.reliable_mode_enabled(),
    )
    return build_runtime_governed_identity(
        operator_surface=EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT,
        policy_payload=policy_payload,
        control_bundle=control_bundle,
    )


async def begin_control_plane_execution(
    *,
    control_plane: ExtensionWorkloadControlPlaneService,
    extension: ExtensionRecord,
    workload: _ExtensionManifestEntry,
    workspace: Path,
    artifact_root: Path,
    input_identity: str,
    input_config: dict[str, Any],
    governed_identity: dict[str, Any],
    control_plane_workload_record: dict[str, Any],
    creation_timestamp: str | None = None,
    run_id: str | None = None,
) -> ExtensionWorkloadControlPlaneStart:
    resolved_creation_timestamp, resolved_run_id = (
        (str(creation_timestamp), str(run_id))
        if creation_timestamp is not None and run_id is not None
        else control_plane_identity(
            extension_id=extension.extension_id,
            workload_id=workload.workload_id,
            input_identity=input_identity,
        )
    )
    return await control_plane.begin_execution(
        run_id=resolved_run_id,
        extension_id=extension.extension_id,
        control_plane_workload_record=control_plane_workload_record,
        policy_payload=dict(governed_identity["governed_policy"]),
        configuration_payload={
            "artifact_root": str(artifact_root),
            "config_digest": digest_prefixed(input_config),
            "control_bundle_hash": governed_identity["control_bundle_hash"],
            "department": governed_identity["control_bundle"]["department"],
            "input_identity": governed_identity["control_bundle"]["input_identity"],
            "required_capabilities": list(governed_identity["control_bundle"].get("required_capabilities", [])),
            "workspace_root": str(workspace),
        },
        admission_decision_receipt_ref=f"extension-workload-admission:{governed_identity['control_bundle_hash']}",
        creation_timestamp=resolved_creation_timestamp,
    )


def control_plane_identity(*, extension_id: str, workload_id: str, input_identity: str) -> tuple[str, str]:
    creation_timestamp = datetime.now(UTC).isoformat()
    run_id = ExtensionWorkloadControlPlaneService.run_id_for(
        extension_id=extension_id,
        workload_id=workload_id,
        creation_timestamp=creation_timestamp,
        input_identity=input_identity,
    )
    return creation_timestamp, run_id


async def emit_turn_final_if_needed(*, interaction_context: Any | None, summary: dict[str, Any], workload_id: str) -> None:
    if interaction_context is None:
        return
    await interaction_context.emit_event(StreamEventType.TURN_FINAL, {"authoritative": True, "summary": summary})
    await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload_id))


async def finalize_started_failure(
    *,
    control_plane: ExtensionWorkloadControlPlaneService,
    control_plane_start: ExtensionWorkloadControlPlaneStart,
    prior_step_ref: str,
    failure_class: str,
    side_effect_observed: bool,
    exc: Exception,
) -> None:
    await control_plane.finalize_execution(
        run_id=control_plane_start.run.run_id,
        outcome=ResultClass.FAILED,
        authoritative_result_ref=error_result_ref(control_plane_start.run.run_id, exc),
        authority_sources=[AuthoritySourceClass.ADAPTER_OBSERVATION],
        prior_step_ref=prior_step_ref,
        failure_class=failure_class,
        side_effect_observed=side_effect_observed,
    )


def prior_step_ref(*, control_plane_start: ExtensionWorkloadControlPlaneStart, capability_steps: Sequence[Any]) -> str:
    if capability_steps and getattr(capability_steps[-1], "output_ref", None):
        return str(capability_steps[-1].output_ref)
    return control_plane_start.start_step.output_ref or control_plane_start.start_step.step_id


def sdk_result_class(
    *,
    subprocess_error: SdkSubprocessRunError | None,
    capability_report: dict[str, Any],
    run_result: dict[str, Any],
) -> ResultClass:
    if any(str(record.get("observed_result") or "") == "blocked" for record in capability_report.get("call_records", [])):
        return ResultClass.BLOCKED
    if subprocess_error is not None or str(run_result.get("status") or "").strip().lower() == "error":
        return ResultClass.FAILED
    return ResultClass.SUCCESS


def sdk_failure_class(*, subprocess_error: SdkSubprocessRunError | None, capability_report: dict[str, Any]) -> str:
    blocked_reason = next(
        (
            str(record.get("denial_class") or record.get("error_code") or "").strip()
            for record in capability_report.get("call_records", [])
            if str(record.get("observed_result") or "") == "blocked"
        ),
        "",
    )
    if blocked_reason:
        return f"sdk_capability_{blocked_reason}"
    if subprocess_error is not None:
        return f"sdk_workload_{subprocess_error.error_code or type(subprocess_error).__name__}"
    return "sdk_workload_failed"


def sdk_side_effect_observed(*, capability_report: dict[str, Any]) -> bool:
    return any(bool(record.get("side_effect_observed")) for record in capability_report.get("call_records", []))


def sdk_closeout_ref(run_id: str, outcome: ResultClass, artifact_manifest_hash: str) -> str:
    if outcome is ResultClass.BLOCKED:
        return f"{run_id}:closeout:blocked"
    if artifact_manifest_hash:
        return artifact_manifest_hash
    return f"{run_id}:closeout:failed"


def error_result_ref(run_id: str, exc: Exception) -> str:
    return f"{run_id}:error:{type(exc).__name__}"


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))


def digest_file(path: Path) -> str:
    return digest_prefixed(path.read_bytes())


__all__ = [
    "begin_control_plane_execution",
    "build_governed_identity",
    "build_sdk_context",
    "compile_workload",
    "control_plane_identity",
    "digest_file",
    "emit_default_model_events",
    "emit_turn_final_if_needed",
    "error_result_ref",
    "execute_plan_actions",
    "finalize_started_failure",
    "prior_step_ref",
    "sdk_closeout_ref",
    "sdk_failure_class",
    "sdk_result_class",
    "sdk_side_effect_observed",
    "write_json_file",
]
