from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Callable

from orket_extension_sdk.result import WorkloadResult
from orket_extension_sdk.workload import run_workload as sdk_run_workload
from orket.streaming.contracts import CommitIntent, StreamEventType

from .contracts import ExtensionRegistry, RunPlan
from .governed_identity import (
    EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT,
    build_extension_control_bundle,
    build_extension_policy_payload,
    build_governed_identity,
    digest_prefixed,
)
from .import_guard import ImportGuardContext
from .models import ExtensionRecord, ExtensionRunResult, WorkloadRecord
from .reproducibility import ReproducibilityEnforcer
from .runtime import ExtensionEngineAdapter, RunContext
from .workload_artifacts import WorkloadArtifacts
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

    async def run_legacy_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload: WorkloadRecord,
        control_plane_workload_record: dict[str, Any],
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        loaded_workload = self.loader.load_legacy_workload(extension, workload.workload_id)
        run_plan = self._compile_workload(loaded_workload, input_config, interaction_context)
        if run_plan.workload_id != workload.workload_id:
            raise ValueError("RunPlan workload_id mismatch")

        if self.artifacts.reproducibility.reliable_mode_enabled():
            self.artifacts.reproducibility.validate_required_materials(loaded_workload.required_materials())
            self.artifacts.reproducibility.validate_clean_git_if_required()

        plan_hash = run_plan.plan_hash()
        artifact_root = self.artifacts.artifact_root(
            extension.extension_id, workload.workload_id, plan_hash, input_config
        )
        artifact_root.mkdir(parents=True, exist_ok=True)

        run_result = await self._execute_plan_actions(
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
        if interaction_context is not None:
            await interaction_context.emit_event(
                StreamEventType.TURN_FINAL, {"authoritative": False, "summary": summary}
            )
            await interaction_context.request_commit(
                CommitIntent(type="turn_finalize", ref=workload.workload_id)
            )

        governed_identity = self._build_governed_identity(
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint="",
            required_capabilities=[],
            contract_style=extension.contract_style,
            department=department,
            input_identity=plan_hash,
        )
        artifact_manifest = await asyncio.to_thread(
            self.artifacts.build_artifact_manifest,
            artifact_root,
            plan_hash=plan_hash,
            governed_identity=governed_identity,
        )
        artifact_manifest_path = artifact_root / "artifact_manifest.json"
        await asyncio.to_thread(self._write_json_file, artifact_manifest_path, artifact_manifest)

        provenance = await asyncio.to_thread(
            self.artifacts.build_provenance,
            extension=extension,
            workload=loaded_workload,
            manifest_workload=workload,
            input_config=input_config,
            run_plan=run_plan,
            plan_hash=plan_hash,
            run_result=run_result,
            summary=summary,
            artifact_manifest=artifact_manifest,
            artifact_root=artifact_root,
            department=department,
            control_plane_workload_record=control_plane_workload_record,
        )
        provenance_path = artifact_root / "provenance.json"
        await asyncio.to_thread(self._write_json_file, provenance_path, provenance)
        artifact_manifest_hash = f"sha256:{str(artifact_manifest.get('manifest_sha256') or '').strip()}"
        provenance_hash = await asyncio.to_thread(self._digest_file, provenance_path)

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
            operator_surface=EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT,
            policy_digest=governed_identity["policy_digest"],
            control_bundle_hash=governed_identity["control_bundle_hash"],
            artifact_manifest_path=str(artifact_manifest_path),
            artifact_manifest_hash=artifact_manifest_hash,
            provenance_hash=provenance_hash,
            determinism_class=governed_identity["determinism_class"],
            control_plane_workload_record=dict(control_plane_workload_record),
        )

    async def run_sdk_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload: WorkloadRecord,
        control_plane_workload_record: dict[str, Any],
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        artifact_root = self.artifacts.artifact_root(
            extension.extension_id, workload.workload_id, input_digest, input_config
        )
        artifact_root.mkdir(parents=True, exist_ok=True)
        capability_registry = self.artifacts.build_sdk_capability_registry(
            workspace=workspace,
            artifact_root=artifact_root,
            input_config=input_config,
        )
        missing_capabilities = capability_registry.preflight(list(workload.required_capabilities))
        if missing_capabilities:
            raise ValueError("E_SDK_CAPABILITY_MISSING: " + ", ".join(missing_capabilities))

        if interaction_context is not None:
            await self._emit_default_model_events(interaction_context, sdk=True)

        sdk_ctx = self._build_sdk_context(
            extension, workload, input_config, workspace, artifact_root, capability_registry, input_digest
        )
        with ImportGuardContext():
            sdk_workload = self.loader.load_sdk_workload(extension, workload)
            result = await self._invoke_sdk_workload(sdk_workload, sdk_ctx, dict(input_config))
        await asyncio.to_thread(self.artifacts.validate_sdk_artifacts, result, artifact_root)

        run_result: dict[str, Any] = {
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

        if interaction_context is not None:
            await interaction_context.emit_event(
                StreamEventType.TURN_FINAL, {"authoritative": False, "summary": summary}
            )
            await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload.workload_id))

        governed_identity = self._build_governed_identity(
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint=workload.entrypoint,
            required_capabilities=list(workload.required_capabilities),
            contract_style=workload.contract_style or extension.contract_style,
            department=department,
            input_identity=input_digest,
        )
        artifact_manifest = await asyncio.to_thread(
            self.artifacts.build_artifact_manifest,
            artifact_root,
            plan_hash=input_digest,
            governed_identity=governed_identity,
        )
        artifact_manifest_path = artifact_root / "artifact_manifest.json"
        await asyncio.to_thread(self._write_json_file, artifact_manifest_path, artifact_manifest)

        provenance = await asyncio.to_thread(
            self.artifacts.build_sdk_provenance,
            extension=extension,
            workload=workload,
            input_config=input_config,
            input_digest=input_digest,
            run_result=run_result,
            summary=summary,
            artifact_manifest=artifact_manifest,
            artifact_root=artifact_root,
            department=department,
            control_plane_workload_record=control_plane_workload_record,
        )
        provenance_path = artifact_root / "provenance.json"
        await asyncio.to_thread(self._write_json_file, provenance_path, provenance)
        artifact_manifest_hash = f"sha256:{str(artifact_manifest.get('manifest_sha256') or '').strip()}"
        provenance_hash = await asyncio.to_thread(self._digest_file, provenance_path)

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
            operator_surface=EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT,
            policy_digest=governed_identity["policy_digest"],
            control_bundle_hash=governed_identity["control_bundle_hash"],
            artifact_manifest_path=str(artifact_manifest_path),
            artifact_manifest_hash=artifact_manifest_hash,
            provenance_hash=provenance_hash,
            determinism_class=governed_identity["determinism_class"],
            control_plane_workload_record=dict(control_plane_workload_record),
        )

    def _compile_workload(
        self, workload: Any, input_config: dict[str, Any], interaction_context: Any | None
    ) -> RunPlan:
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

    async def _execute_plan_actions(
        self,
        *,
        run_plan: RunPlan,
        workspace: Path,
        department: str,
        interaction_context: Any | None,
    ) -> dict[str, Any]:
        action_results: list[dict[str, Any]] = []
        if interaction_context is not None:
            await self._emit_default_model_events(interaction_context, sdk=False)
        if run_plan.actions:
            adapter = ExtensionEngineAdapter(RunContext(workspace=workspace, department=department))
            for action in run_plan.actions:
                action_results.append(await adapter.execute_action(action))
        return {
            "plan_hash": run_plan.plan_hash(),
            "action_count": len(run_plan.actions),
            "action_results": action_results,
        }

    @staticmethod
    async def _emit_default_model_events(interaction_context: Any, *, sdk: bool) -> None:
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

    @staticmethod
    def _build_sdk_context(
        extension: ExtensionRecord,
        workload: WorkloadRecord,
        input_config: dict[str, Any],
        workspace: Path,
        artifact_root: Path,
        capability_registry: Any,
        input_digest: str,
    ) -> Any:
        from orket_extension_sdk.workload import WorkloadContext as SDKWorkloadContext

        return SDKWorkloadContext(
            extension_id=extension.extension_id,
            workload_id=workload.workload_id,
            run_id=f"sdk-{input_digest[:16]}",
            workspace_root=workspace,
            input_dir=workspace,
            output_dir=artifact_root,
            capabilities=capability_registry,
            seed=int(input_config.get("seed", 0) or 0),
            config=dict(input_config),
        )

    @staticmethod
    async def _invoke_sdk_workload(sdk_workload: Any, sdk_ctx: Any, input_payload: dict[str, Any]) -> WorkloadResult:
        run_method = getattr(sdk_workload, "run", None)
        if run_method is not None and inspect.iscoroutinefunction(run_method):
            result = await run_method(sdk_ctx, input_payload)
            if not isinstance(result, WorkloadResult):
                raise ValueError("E_SDK_WORKLOAD_RESULT_INVALID")
            return result
        return await asyncio.to_thread(sdk_run_workload, sdk_workload, sdk_ctx, input_payload)

    def _build_governed_identity(
        self,
        *,
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
            reliable_mode_enabled=self.artifacts.reproducibility.reliable_mode_enabled(),
            reliable_require_clean_git=self.artifacts.reliable_require_clean_git_enabled(),
            provenance_verbose_enabled=self.artifacts.provenance_verbose_enabled(),
            artifact_file_size_cap_bytes=self.artifacts.artifact_file_size_cap_bytes(),
            artifact_total_size_cap_bytes=self.artifacts.artifact_total_size_cap_bytes(),
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
            reliable_mode_enabled=self.artifacts.reproducibility.reliable_mode_enabled(),
        )
        return build_governed_identity(
            operator_surface=EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT,
            policy_payload=policy_payload,
            control_bundle=control_bundle,
        )

    @staticmethod
    def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"))

    @staticmethod
    def _digest_file(path: Path) -> str:
        return digest_prefixed(path.read_bytes())
