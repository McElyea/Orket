from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Callable

from orket_extension_sdk.workload import run_workload as sdk_run_workload
from orket.streaming.contracts import CommitIntent, StreamEventType

from .contracts import ExtensionRegistry, RunPlan
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
        workload_id: str,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        workload = self.loader.load_legacy_workload(extension, workload_id)
        run_plan = self._compile_workload(workload, input_config, interaction_context)
        if run_plan.workload_id != workload_id:
            raise ValueError("RunPlan workload_id mismatch")

        if self.artifacts.reproducibility.reliable_mode_enabled():
            self.artifacts.reproducibility.validate_required_materials(workload.required_materials())
            self.artifacts.reproducibility.validate_clean_git_if_required()

        plan_hash = run_plan.plan_hash()
        artifact_root = self.artifacts.artifact_root(extension.extension_id, workload.workload_id, plan_hash, input_config)
        artifact_root.mkdir(parents=True, exist_ok=True)

        run_result = await self._execute_plan_actions(
            run_plan=run_plan,
            workspace=workspace,
            department=department,
            interaction_context=interaction_context,
        )
        validation_errors = self.artifacts.run_validators(workload, run_result, artifact_root)
        if validation_errors:
            raise RuntimeError("Post-run validation failed: " + "; ".join(validation_errors))

        summary = workload.summarize({"run_result": run_result, "artifact_root": str(artifact_root)})
        if not isinstance(summary, dict):
            raise TypeError("summarize(run_artifacts) must return a dict")
        if interaction_context is not None:
            await interaction_context.emit_event(StreamEventType.TURN_FINAL, {"authoritative": False, "summary": summary})
            await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload_id))

        artifact_manifest = self.artifacts.build_artifact_manifest(artifact_root)
        (artifact_root / "artifact_manifest.json").write_text(
            json.dumps(artifact_manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        provenance = self.artifacts.build_provenance(
            extension=extension,
            workload=workload,
            input_config=input_config,
            run_plan=run_plan,
            plan_hash=plan_hash,
            run_result=run_result,
            summary=summary,
            artifact_manifest=artifact_manifest,
            artifact_root=artifact_root,
        )
        provenance_path = artifact_root / "provenance.json"
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")

        return ExtensionRunResult(
            extension_id=extension.extension_id,
            extension_version=extension.extension_version,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            plan_hash=plan_hash,
            artifact_root=str(artifact_root),
            provenance_path=str(provenance_path),
            summary=summary,
        )

    async def run_sdk_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload: WorkloadRecord,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        sdk_workload = self.loader.load_sdk_workload(extension, workload)
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        artifact_root = self.artifacts.artifact_root(extension.extension_id, workload.workload_id, input_digest, input_config)
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

        result = sdk_run_workload(
            sdk_workload,
            self._build_sdk_context(extension, workload, input_config, workspace, artifact_root, capability_registry, input_digest),
            dict(input_config),
        )
        self.artifacts.validate_sdk_artifacts(result, artifact_root)

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
            await interaction_context.emit_event(StreamEventType.TURN_FINAL, {"authoritative": False, "summary": summary})
            await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload.workload_id))

        artifact_manifest = self.artifacts.build_artifact_manifest(artifact_root)
        (artifact_root / "artifact_manifest.json").write_text(
            json.dumps(artifact_manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        provenance = self.artifacts.build_sdk_provenance(
            extension=extension,
            workload=workload,
            input_config=input_config,
            input_digest=input_digest,
            run_result=run_result,
            summary=summary,
            artifact_manifest=artifact_manifest,
            artifact_root=artifact_root,
            department=department,
        )
        provenance_path = artifact_root / "provenance.json"
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")

        return ExtensionRunResult(
            extension_id=extension.extension_id,
            extension_version=extension.extension_version,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            plan_hash=input_digest,
            artifact_root=str(artifact_root),
            provenance_path=str(provenance_path),
            summary=summary,
        )

    def _compile_workload(self, workload: Any, input_config: dict[str, Any], interaction_context: Any | None) -> RunPlan:
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
