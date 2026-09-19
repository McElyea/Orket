from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.workload_artifact_store import prepare_artifact_root
from orket.application.services.extension_workload_control_plane_service import (
    ExtensionWorkloadControlPlaneService,
    build_extension_workload_control_plane_service,
)
from orket.core.domain import AuthoritySourceClass, ResultClass
from orket_extension_sdk.manifest import agent_discriminator_reasons

from .contracts import ExtensionRegistry
from .models import ExtensionRecord, ExtensionRunResult, _ExtensionManifestEntry
from .reproducibility import ReproducibilityEnforcer
from .sdk_capability_authorization import build_host_authorization_envelope, split_host_capability_controls
from .sdk_workload_runner import SdkSubprocessExecutionUncertain, SdkSubprocessRunError, run_sdk_workload_in_subprocess
from .workload_artifacts import WorkloadArtifacts
from .workload_executor_support import (
    begin_control_plane_execution,
    build_governed_identity,
    build_sdk_context,
    control_plane_identity,
    emit_default_model_events,
    execute_plan_actions,
    finalize_started_failure,
    prior_step_ref,
    sdk_closeout_ref,
    sdk_failure_class,
    sdk_result_class,
    sdk_side_effect_observed,
)
from .workload_loader import WorkloadLoader
from .workload_policy import capture_workload_policy
from .workload_publication import prepare_legacy_workload, publish_manifest, publish_provenance


class WorkloadExecutor:
    """Executes both legacy and SDK extension workloads."""

    def __init__(
        self,
        *,
        project_root: Path,
        reproducibility: ReproducibilityEnforcer,
        registry_factory: Callable[[], ExtensionRegistry],
    ) -> None:
        self.loader = WorkloadLoader(registry_factory)
        self.artifacts = WorkloadArtifacts(project_root, reproducibility)
        self.control_plane = build_extension_workload_control_plane_service(project_root=project_root)

    async def run_legacy_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload: _ExtensionManifestEntry,
        control_plane_workload_record: dict[str, Any],
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        policy = capture_workload_policy()
        input_config, control_plane_workload_record = deepcopy(input_config), deepcopy(control_plane_workload_record)
        loaded_workload, run_plan = await prepare_legacy_workload(
            self.loader, self.artifacts, extension, workload, input_config, interaction_context, policy=policy)

        plan_hash = run_plan.plan_hash()
        artifact_root = self.artifacts.artifact_root(extension.extension_id, workload.workload_id, plan_hash, input_config)
        governed_identity = build_governed_identity(
            policy=policy,
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint="",
            required_capabilities=[],
            contract_style=extension.contract_style,
            department=department,
            input_identity=plan_hash,
        )
        await run_owned_thread(partial(prepare_artifact_root, artifact_root), label="legacy-artifact-root")
        control_plane_start = await begin_control_plane_execution(
            control_plane=self.control_plane,
            extension=extension,
            workload=workload,
            workspace=workspace,
            artifact_root=artifact_root,
            input_identity=plan_hash,
            input_config=input_config,
            governed_identity=governed_identity,
            control_plane_workload_record=control_plane_workload_record,
        )

        closeout = None
        try:
            run_result = await execute_plan_actions(
                run_plan=run_plan,
                workspace=workspace,
                department=department,
                interaction_context=interaction_context,
            )
            validation_errors = await run_owned_thread(
                partial(self.artifacts.run_validators, loaded_workload, run_result, artifact_root),
                label="legacy-workload-validation")
            if validation_errors:
                raise RuntimeError("Post-run validation failed: " + "; ".join(validation_errors))
            summary = await run_owned_thread(
                partial(loaded_workload.summarize, {"run_result": run_result, "artifact_root": str(artifact_root)}),
                label="legacy-workload-summary")
            if not isinstance(summary, dict):
                raise TypeError("summarize(run_artifacts) must return a dict")
            artifact_manifest, artifact_manifest_path, artifact_manifest_hash = await publish_manifest(
                self.artifacts, artifact_root, plan_hash=plan_hash, governed_identity=governed_identity, policy=policy)
            closeout = await self.control_plane.finalize_execution(
                run_id=control_plane_start.run.run_id,
                outcome=ResultClass.SUCCESS,
                authoritative_result_ref=artifact_manifest_hash,
                authority_sources=[AuthoritySourceClass.VALIDATED_ARTIFACT],
                prior_step_ref=prior_step_ref(control_plane_start=control_plane_start, capability_steps=()),
            )
            control_plane = ExtensionWorkloadControlPlaneService.projection_from_records(
                start=control_plane_start,
                capability_steps=(),
                capability_effects=(),
                closeout=closeout,
            )
            provenance_path, provenance_hash = await publish_provenance(partial(
                self.artifacts.build_provenance, policy=policy,
                extension=extension,
                workload=loaded_workload,
                manifest_entry=workload,
                input_config=input_config,
                run_plan=run_plan,
                plan_hash=plan_hash,
                run_result=run_result,
                summary=summary,
                artifact_manifest=artifact_manifest,
                artifact_root=artifact_root,
                department=department,
                control_plane_workload_record=control_plane_workload_record,
                control_plane_execution=control_plane,
            ), artifact_root)
        except Exception as exc:
            if closeout is not None:
                raise  # Projection failure cannot replace an already confirmed execution outcome.
            await finalize_started_failure(
                control_plane=self.control_plane,
                control_plane_start=control_plane_start,
                prior_step_ref=prior_step_ref(control_plane_start=control_plane_start, capability_steps=()),
                failure_class=f"extension_workload_{type(exc).__name__}",
                side_effect_observed=False,
                exc=exc,
            )
            raise

        return ExtensionRunResult(
            extension_id=extension.extension_id,
            extension_version=extension.extension_version,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            plan_hash=plan_hash,
            artifact_root=str(artifact_root),
            provenance_path=str(provenance_path),
            summary=summary,
            claim_tier=governed_identity["claim_tier"],
            compare_scope=governed_identity["compare_scope"],
            operator_surface="extension_run_result_identity_v1",
            policy_digest=governed_identity["policy_digest"],
            control_bundle_hash=governed_identity["control_bundle_hash"],
            artifact_manifest_path=str(artifact_manifest_path),
            artifact_manifest_hash=artifact_manifest_hash,
            provenance_hash=provenance_hash,
            determinism_class=governed_identity["determinism_class"],
            control_plane_workload_record=dict(control_plane_workload_record),
            control_plane=control_plane,
        )

    async def run_sdk_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload: _ExtensionManifestEntry,
        control_plane_workload_record: dict[str, Any],
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        policy = capture_workload_policy()
        input_config, control_plane_workload_record = deepcopy(input_config), deepcopy(control_plane_workload_record)
        agent_markers = agent_discriminator_reasons(
            {
                "workload_id": workload.workload_id,
                "workload_kind": workload.workload_kind,
                "required_capabilities": list(workload.required_capabilities),
                "input_contract": workload.input_contract,
                "output_contract": workload.output_contract,
                "agent": workload.agent_declaration or None,
            }
        )
        if agent_markers:
            raise ValueError("E_AGENT_RUNTIME_NOT_ADMITTED: governed_agent_loop.v1")
        runtime_input_config, host_controls = split_host_capability_controls(dict(input_config))
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        artifact_root = self.artifacts.artifact_root(extension.extension_id, workload.workload_id, input_digest, input_config)
        governed_identity = build_governed_identity(
            policy=policy,
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint=workload.entrypoint,
            required_capabilities=list(workload.required_capabilities),
            contract_style=workload.contract_style or extension.contract_style,
            department=department,
            input_identity=input_digest,
        )
        creation_timestamp, run_id = control_plane_identity(
            extension_id=extension.extension_id,
            workload_id=workload.workload_id,
            input_identity=input_digest,
        )
        authorization_envelope = build_host_authorization_envelope(
            extension_id=extension.extension_id,
            workload_id=workload.workload_id,
            run_id=run_id,
            declared_capabilities=list(workload.required_capabilities),
            controls=host_controls,
        )
        capability_registry = self.artifacts.build_sdk_capability_registry(
            workspace=workspace,
            artifact_root=artifact_root,
            input_config=runtime_input_config,
            extension_id=extension.extension_id,
            admitted_capabilities=set(authorization_envelope.admitted_capabilities),
        )
        module_name, _attr_name = WorkloadLoader.parse_sdk_entrypoint(workload.entrypoint)
        await run_owned_thread(partial(prepare_artifact_root, artifact_root), label="sdk-artifact-root")
        await run_owned_thread(
            lambda: self.loader.validate_extension_imports(Path(extension.path), module_name,
                allowed_stdlib_modules=extension.allowed_stdlib_modules, enforce_declared_stdlib=True),
            label="sdk-extension-source-validation",
        )
        control_plane_start = await begin_control_plane_execution(
            control_plane=self.control_plane,
            extension=extension,
            workload=workload,
            workspace=workspace,
            artifact_root=artifact_root,
            input_identity=input_digest,
            input_config=input_config,
            governed_identity=governed_identity,
            control_plane_workload_record=control_plane_workload_record,
            creation_timestamp=creation_timestamp,
            run_id=run_id,
        )
        if interaction_context is not None:
            await emit_default_model_events(interaction_context, sdk=True)
        sdk_ctx = build_sdk_context(
            extension,
            workload,
            runtime_input_config,
            workspace,
            artifact_root,
            capability_registry,
            run_id,
        )

        subprocess_error: SdkSubprocessRunError | None = None
        capability_report: dict[str, Any] = {}
        capability_steps: tuple[Any, ...] = ()
        capability_effects: tuple[Any, ...] = ()
        try:
            subprocess_result = await run_sdk_workload_in_subprocess(
                extension=extension,
                workload=workload,
                sdk_ctx=sdk_ctx,
                input_payload=dict(runtime_input_config),
                authorization_envelope=authorization_envelope,
                audit_case=host_controls.audit_case,
                child_extra_capabilities=host_controls.child_extra_capabilities,
            )
            capability_report = subprocess_result.capability_report
            capability_steps, capability_effects = await self.control_plane.publish_sdk_capability_calls(
                run_id=run_id,
                extension_id=extension.extension_id,
                call_records=list(capability_report.get("call_records") or []),
            )
            result = subprocess_result.workload_result
            await run_owned_thread(partial(self.artifacts.validate_sdk_artifacts, result, artifact_root, policy=policy),
                                   label="sdk-artifact-validation")
            run_result = {
                "status": "ok" if result.ok else "error",
                "output": result.output,
                "issues": [issue.model_dump(mode="json") for issue in result.issues],
                "artifacts": [artifact.model_dump(mode="json") for artifact in result.artifacts],
                "metrics": result.metrics,
            }
            summary = {
                "ok": result.ok,
                "status": run_result["status"],
                "output": result.output,
                "issue_count": len(result.issues),
                "artifact_count": len(result.artifacts),
            }
        except SdkSubprocessRunError as exc:
            subprocess_error = exc
            capability_report = dict(exc.capability_report)
            capability_steps, capability_effects = await self.control_plane.publish_sdk_capability_calls(
                run_id=run_id,
                extension_id=extension.extension_id,
                call_records=list(capability_report.get("call_records") or []),
            )
            run_result = {
                "status": "error",
                "output": {},
                "issues": [
                    {
                        "code": exc.error_code or "sdk_workload_subprocess_failed",
                        "message": str(exc),
                        "severity": "error",
                    }
                ],
                "artifacts": [],
                "metrics": {},
            }
            summary = {"ok": False, "status": "error", "output": {}, "issue_count": 1, "artifact_count": 0}
        except SdkSubprocessExecutionUncertain:
            raise  # Keep the existing nonterminal run and resume-forbidden checkpoint.
        except Exception as exc:
            await finalize_started_failure(
                control_plane=self.control_plane,
                control_plane_start=control_plane_start,
                prior_step_ref=prior_step_ref(control_plane_start=control_plane_start, capability_steps=capability_steps),
                failure_class=f"sdk_workload_{type(exc).__name__}",
                side_effect_observed=sdk_side_effect_observed(capability_report=capability_report),
                exc=exc,
            )
            raise

        closeout = None
        try:
            artifact_manifest, artifact_manifest_path, artifact_manifest_hash = await publish_manifest(
                self.artifacts, artifact_root, plan_hash=input_digest, governed_identity=governed_identity, policy=policy)
            outcome = sdk_result_class(
                subprocess_error=subprocess_error,
                capability_report=capability_report,
                run_result=run_result,
            )
            closeout = await self.control_plane.finalize_execution(
                run_id=run_id,
                outcome=outcome,
                authoritative_result_ref=(
                    artifact_manifest_hash
                    if outcome is ResultClass.SUCCESS
                    else sdk_closeout_ref(run_id, outcome, artifact_manifest_hash)
                ),
                authority_sources=(
                    [AuthoritySourceClass.VALIDATED_ARTIFACT]
                    if outcome is ResultClass.SUCCESS
                    else [AuthoritySourceClass.ADAPTER_OBSERVATION]
                ),
                prior_step_ref=prior_step_ref(
                    control_plane_start=control_plane_start,
                    capability_steps=capability_steps,
                ),
                failure_class=sdk_failure_class(
                    subprocess_error=subprocess_error,
                    capability_report=capability_report,
                ),
                side_effect_observed=sdk_side_effect_observed(capability_report=capability_report),
            )
            control_plane = ExtensionWorkloadControlPlaneService.projection_from_records(
                start=control_plane_start,
                capability_steps=capability_steps,
                capability_effects=capability_effects,
                closeout=closeout,
            )
            provenance_path, provenance_hash = await publish_provenance(partial(
                self.artifacts.build_sdk_provenance, policy=policy,
                extension=extension,
                workload=workload,
                input_config=runtime_input_config,
                input_digest=input_digest,
                run_result=run_result,
                summary=summary,
                artifact_manifest=artifact_manifest,
                artifact_root=artifact_root,
                department=department,
                control_plane_workload_record=control_plane_workload_record,
                sdk_capability_report=capability_report,
                control_plane_execution=control_plane,
            ), artifact_root)
        except Exception as exc:
            if closeout is not None:
                raise  # Projection failure cannot replace an already confirmed execution outcome.
            await finalize_started_failure(
                control_plane=self.control_plane,
                control_plane_start=control_plane_start,
                prior_step_ref=prior_step_ref(
                    control_plane_start=control_plane_start,
                    capability_steps=capability_steps,
                ),
                failure_class=f"sdk_workload_{type(exc).__name__}",
                side_effect_observed=sdk_side_effect_observed(capability_report=capability_report),
                exc=exc,
            )
            raise

        if subprocess_error is not None:
            raise subprocess_error

        return ExtensionRunResult(
            extension_id=extension.extension_id,
            extension_version=extension.extension_version,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            plan_hash=input_digest,
            artifact_root=str(artifact_root),
            provenance_path=str(provenance_path),
            summary=summary,
            claim_tier=governed_identity["claim_tier"],
            compare_scope=governed_identity["compare_scope"],
            operator_surface="extension_run_result_identity_v1",
            policy_digest=governed_identity["policy_digest"],
            control_bundle_hash=governed_identity["control_bundle_hash"],
            artifact_manifest_path=str(artifact_manifest_path),
            artifact_manifest_hash=artifact_manifest_hash,
            provenance_hash=provenance_hash,
            determinism_class=governed_identity["determinism_class"],
            control_plane_workload_record=dict(control_plane_workload_record),
            control_plane=control_plane,
        )
