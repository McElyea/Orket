from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from orket.application.services.extension_workload_control_plane_service import (
    ExtensionWorkloadControlPlaneService,
    build_extension_workload_control_plane_service,
)
from orket.core.domain import AuthoritySourceClass, ResultClass

from .contracts import ExtensionRegistry
from .models import ExtensionRecord, ExtensionRunResult, _ExtensionManifestEntry
from .reproducibility import ReproducibilityEnforcer
from .sdk_capability_authorization import build_host_authorization_envelope, split_host_capability_controls
from .sdk_workload_runner import SdkSubprocessRunError, run_sdk_workload_in_subprocess
from .workload_artifacts import WorkloadArtifacts
from .workload_executor_support import (
    begin_control_plane_execution,
    build_governed_identity,
    build_sdk_context,
    compile_workload,
    control_plane_identity,
    digest_file,
    emit_default_model_events,
    emit_turn_final_if_needed,
    execute_plan_actions,
    finalize_started_failure,
    prior_step_ref,
    sdk_closeout_ref,
    sdk_failure_class,
    sdk_result_class,
    sdk_side_effect_observed,
    write_json_file,
)
from .workload_loader import WorkloadLoader


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

    def _compile_workload(self, workload: Any, input_config: dict[str, Any], interaction_context: Any | None):
        return compile_workload(workload, input_config, interaction_context)

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
        loaded_workload = await asyncio.to_thread(self.loader.load_legacy_workload, extension, workload.workload_id)
        run_plan = compile_workload(loaded_workload, input_config, interaction_context)
        if run_plan.workload_id != workload.workload_id:
            raise ValueError("RunPlan workload_id mismatch")
        if self.artifacts.reproducibility.reliable_mode_enabled():
            self.artifacts.reproducibility.validate_required_materials(loaded_workload.required_materials())
            self.artifacts.reproducibility.validate_clean_git_if_required()

        plan_hash = run_plan.plan_hash()
        artifact_root = self.artifacts.artifact_root(extension.extension_id, workload.workload_id, plan_hash, input_config)
        artifact_root.mkdir(parents=True, exist_ok=True)
        governed_identity = build_governed_identity(
            artifacts=self.artifacts,
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint="",
            required_capabilities=[],
            contract_style=extension.contract_style,
            department=department,
            input_identity=plan_hash,
        )
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

        try:
            run_result = await execute_plan_actions(
                run_plan=run_plan,
                workspace=workspace,
                department=department,
                interaction_context=interaction_context,
            )
            validation_errors = self.artifacts.run_validators(loaded_workload, run_result, artifact_root)
            if validation_errors:
                raise RuntimeError("Post-run validation failed: " + "; ".join(validation_errors))
            summary = loaded_workload.summarize({"run_result": run_result, "artifact_root": str(artifact_root)})
            if not isinstance(summary, dict):
                raise TypeError("summarize(run_artifacts) must return a dict")
            await emit_turn_final_if_needed(
                interaction_context=interaction_context,
                summary=summary,
                workload_id=workload.workload_id,
            )
            artifact_manifest = await asyncio.to_thread(
                self.artifacts.build_artifact_manifest,
                artifact_root,
                plan_hash=plan_hash,
                governed_identity=governed_identity,
            )
            artifact_manifest_path = artifact_root / "artifact_manifest.json"
            await asyncio.to_thread(write_json_file, artifact_manifest_path, artifact_manifest)
            artifact_manifest_hash = f"sha256:{str(artifact_manifest.get('manifest_sha256') or '').strip()}"
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
            provenance = await asyncio.to_thread(
                self.artifacts.build_provenance,
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
            )
            provenance_path = artifact_root / "provenance.json"
            await asyncio.to_thread(write_json_file, provenance_path, provenance)
            provenance_hash = await asyncio.to_thread(digest_file, provenance_path)
        except Exception as exc:
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
        runtime_input_config, host_controls = split_host_capability_controls(dict(input_config))
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        artifact_root = self.artifacts.artifact_root(extension.extension_id, workload.workload_id, input_digest, input_config)
        artifact_root.mkdir(parents=True, exist_ok=True)
        governed_identity = build_governed_identity(
            artifacts=self.artifacts,
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
        await asyncio.to_thread(
            self.loader.validate_extension_imports,
            Path(extension.path),
            module_name,
            allowed_stdlib_modules=extension.allowed_stdlib_modules,
            enforce_declared_stdlib=True,
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
            await asyncio.to_thread(self.artifacts.validate_sdk_artifacts, result, artifact_root)
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
        except Exception as exc:
            await finalize_started_failure(
                control_plane=self.control_plane,
                control_plane_start=control_plane_start,
                prior_step_ref=prior_step_ref(control_plane_start=control_plane_start, capability_steps=()),
                failure_class=f"sdk_workload_{type(exc).__name__}",
                side_effect_observed=False,
                exc=exc,
            )
            raise

        if subprocess_error is None:
            await emit_turn_final_if_needed(
                interaction_context=interaction_context,
                summary=summary,
                workload_id=workload.workload_id,
            )

        try:
            artifact_manifest = await asyncio.to_thread(
                self.artifacts.build_artifact_manifest,
                artifact_root,
                plan_hash=input_digest,
                governed_identity=governed_identity,
            )
            artifact_manifest_path = artifact_root / "artifact_manifest.json"
            await asyncio.to_thread(write_json_file, artifact_manifest_path, artifact_manifest)
            artifact_manifest_hash = f"sha256:{str(artifact_manifest.get('manifest_sha256') or '').strip()}"
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
            provenance = await asyncio.to_thread(
                self.artifacts.build_sdk_provenance,
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
            )
            provenance_path = artifact_root / "provenance.json"
            await asyncio.to_thread(write_json_file, provenance_path, provenance)
            provenance_hash = await asyncio.to_thread(digest_file, provenance_path)
        except Exception as exc:
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
