from __future__ import annotations

import ast
import hashlib
import importlib
from importlib.metadata import entry_points
import inspect
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.manifest import load_manifest as load_sdk_manifest
from orket_extension_sdk.result import WorkloadResult
from orket_extension_sdk.workload import Workload as SDKWorkload
from orket_extension_sdk.workload import WorkloadContext as SDKWorkloadContext
from orket_extension_sdk.workload import run_workload as run_sdk_workload

from orket.runtime_paths import durable_root

from .contracts import ExtensionRegistry, RunPlan, Workload
from .runtime import ExtensionEngineAdapter, RunContext
from orket.streaming.contracts import CommitIntent, StreamEventType

RELIABLE_MODE_ENV = "ORKET_RELIABLE_MODE"
RELIABLE_REQUIRE_CLEAN_GIT_ENV = "ORKET_RELIABLE_REQUIRE_CLEAN_GIT"
LEGACY_MANIFEST_FILENAME = "orket_extension.json"
SDK_MANIFEST_FILENAMES = ("extension.yaml", "extension.yml", "extension.json")
CONTRACT_STYLE_LEGACY = "legacy_v1"
CONTRACT_STYLE_SDK_V0 = "sdk_v0"


def default_extensions_catalog_path() -> Path:
    env_path = (os.getenv("ORKET_EXTENSIONS_CATALOG") or "").strip()
    if env_path:
        return Path(env_path)
    return durable_root() / "config" / "extensions_catalog.json"


@dataclass(frozen=True)
class WorkloadRecord:
    workload_id: str
    workload_version: str
    entrypoint: str = ""
    required_capabilities: tuple[str, ...] = ()
    contract_style: str = CONTRACT_STYLE_LEGACY


@dataclass(frozen=True)
class ExtensionRecord:
    extension_id: str
    extension_version: str
    source: str
    extension_api_version: str
    path: str
    module: str
    register_callable: str
    workloads: tuple[WorkloadRecord, ...]
    contract_style: str = CONTRACT_STYLE_LEGACY
    manifest_path: str = ""


@dataclass(frozen=True)
class ExtensionRunResult:
    extension_id: str
    extension_version: str
    workload_id: str
    workload_version: str
    plan_hash: str
    artifact_root: str
    provenance_path: str
    summary: dict[str, Any]


@dataclass(frozen=True)
class _LoadedManifest:
    payload: dict[str, Any]
    manifest_path: Path
    contract_style: str


class _WorkloadRegistry(ExtensionRegistry):
    def __init__(self):
        self._workloads: dict[str, Workload] = {}

    def register_workload(self, workload: Workload) -> None:
        workload_id = str(getattr(workload, "workload_id", "") or "").strip()
        if not workload_id:
            raise ValueError("workload_id is required")
        self._workloads[workload_id] = workload

    def workloads(self) -> dict[str, Workload]:
        return dict(self._workloads)


class ExtensionManager:
    def __init__(self, catalog_path: Path | None = None, project_root: Path | None = None):
        self.catalog_path = (catalog_path or default_extensions_catalog_path()).resolve()
        self.project_root = (project_root or Path.cwd()).resolve()
        self.install_root = durable_root() / "extensions"
        self.install_root.mkdir(parents=True, exist_ok=True)

    def list_extensions(self) -> list[ExtensionRecord]:
        payload = self._load_catalog_payload()
        rows = list(payload.get("extensions", [])) + self._discover_entry_point_rows()
        records: list[ExtensionRecord] = []
        seen_ids: set[str] = set()
        for row in rows:
            extension_id = str(row.get("extension_id", "")).strip()
            extension_version = str(row.get("extension_version", "")).strip() or "0.0.0"
            source = str(row.get("source", "")).strip() or "unknown"
            extension_api_version = str(row.get("extension_api_version", "")).strip() or "1.0.0"
            path = str(row.get("path", "")).strip()
            module = str(row.get("module", "")).strip()
            register_callable = str(row.get("register_callable", "")).strip() or "register"
            contract_style = str(row.get("contract_style", "")).strip() or CONTRACT_STYLE_LEGACY
            manifest_path = str(row.get("manifest_path", "")).strip()
            if not extension_id or extension_id in seen_ids:
                continue
            seen_ids.add(extension_id)

            workloads: list[WorkloadRecord] = []
            for item in row.get("workloads", []):
                workload_id = str(item.get("workload_id", "")).strip()
                if not workload_id:
                    continue
                required_capabilities = tuple(
                    str(cap).strip() for cap in item.get("required_capabilities", []) if str(cap).strip()
                )
                workloads.append(
                    WorkloadRecord(
                        workload_id=workload_id,
                        workload_version=str(item.get("workload_version", "")).strip() or "0.0.0",
                        entrypoint=str(item.get("entrypoint", "")).strip(),
                        required_capabilities=required_capabilities,
                        contract_style=str(item.get("contract_style", "")).strip() or contract_style,
                    )
                )

            records.append(
                ExtensionRecord(
                    extension_id=extension_id,
                    extension_version=extension_version,
                    source=source,
                    extension_api_version=extension_api_version,
                    path=path,
                    module=module,
                    register_callable=register_callable,
                    workloads=tuple(workloads),
                    contract_style=contract_style,
                    manifest_path=manifest_path,
                )
            )
        return records

    def resolve_workload(self, workload_id: str) -> tuple[ExtensionRecord, WorkloadRecord] | None:
        target = str(workload_id or "").strip()
        if not target:
            return None
        for extension in self.list_extensions():
            for workload in extension.workloads:
                if workload.workload_id == target:
                    return extension, workload
        return None

    def install_from_repo(self, repo: str, ref: str | None = None) -> ExtensionRecord:
        repo_value = str(repo or "").strip()
        if not repo_value:
            raise ValueError("repo is required")
        ref_value = str(ref or "").strip()

        source_hash = hashlib.sha256(f"{repo_value}@{ref_value}".encode("utf-8")).hexdigest()[:12]
        leaf = f"{Path(repo_value).stem or 'extension'}-{source_hash}"
        destination = self.install_root / leaf
        if destination.exists():
            shutil.rmtree(destination)

        clone_cmd = ["git", "clone", repo_value, str(destination)]
        self._run_command(clone_cmd, cwd=self.project_root)
        if ref_value:
            self._run_command(["git", "checkout", ref_value], cwd=destination)

        loaded = self._load_manifest(destination)
        record = self._record_from_manifest(
            loaded.payload,
            source=repo_value,
            path=destination,
            contract_style=loaded.contract_style,
            manifest_path=loaded.manifest_path,
        )
        payload = self._load_catalog_payload()
        rows = [row for row in payload.get("extensions", []) if str(row.get("extension_id", "")).strip() != record.extension_id]
        rows.append(self._row_from_record(record))
        self._save_catalog_payload({"extensions": rows})
        return record

    async def run_workload(
        self,
        *,
        workload_id: str,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        resolved = self.resolve_workload(workload_id)
        if resolved is None:
            raise ValueError(f"Unknown workload '{workload_id}'")
        extension, workload_record = resolved
        if workload_record.contract_style == CONTRACT_STYLE_SDK_V0 or extension.contract_style == CONTRACT_STYLE_SDK_V0:
            return await self._run_sdk_workload(
                extension=extension,
                workload=workload_record,
                input_config=input_config,
                workspace=workspace,
                department=department,
                interaction_context=interaction_context,
            )
        return await self._run_legacy_workload(
            extension=extension,
            workload_id=workload_id,
            input_config=input_config,
            workspace=workspace,
            department=department,
            interaction_context=interaction_context,
        )

    async def _run_legacy_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload_id: str,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        workload = self._load_legacy_workload(extension, workload_id)
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
        if run_plan.workload_id != workload_id:
            raise ValueError("RunPlan workload_id mismatch")

        reliable_mode = self._reliable_mode_enabled()
        if reliable_mode:
            self._validate_required_materials(workload.required_materials())
            self._validate_clean_git_if_required()

        plan_hash = run_plan.plan_hash()
        artifact_root = self._artifact_root(extension.extension_id, workload.workload_id, plan_hash, input_config)
        artifact_root.mkdir(parents=True, exist_ok=True)

        action_results: list[dict[str, Any]] = []
        if interaction_context is not None:
            await interaction_context.emit_event(
                StreamEventType.MODEL_SELECTED,
                {"model_id": "extension-default", "reason": "workload_compile", "authoritative": False},
            )
            await interaction_context.emit_event(
                StreamEventType.MODEL_LOADING,
                {"cold_start": False, "progress": 1.0, "authoritative": False},
            )
            await interaction_context.emit_event(
                StreamEventType.MODEL_READY,
                {"model_id": "extension-default", "warm_state": "warm", "load_ms": 0, "authoritative": False},
            )
        if run_plan.actions:
            adapter = ExtensionEngineAdapter(RunContext(workspace=workspace, department=department))
            for action in run_plan.actions:
                action_results.append(await adapter.execute_action(action))

        run_result: dict[str, Any] = {
            "plan_hash": plan_hash,
            "action_count": len(run_plan.actions),
            "action_results": action_results,
        }

        validation_errors = self._run_validators(workload, run_result, artifact_root)
        if validation_errors:
            raise RuntimeError("Post-run validation failed: " + "; ".join(validation_errors))

        summary = workload.summarize({"run_result": run_result, "artifact_root": str(artifact_root)})
        if not isinstance(summary, dict):
            raise TypeError("summarize(run_artifacts) must return a dict")
        if interaction_context is not None:
            await interaction_context.emit_event(
                StreamEventType.TURN_FINAL,
                {"authoritative": False, "summary": summary},
            )
            await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload_id))

        artifact_manifest = self._build_artifact_manifest(artifact_root)
        manifest_path = artifact_root / "artifact_manifest.json"
        manifest_path.write_text(json.dumps(artifact_manifest, indent=2, sort_keys=True), encoding="utf-8")

        provenance = self._build_provenance(
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

    async def _run_sdk_workload(
        self,
        *,
        extension: ExtensionRecord,
        workload: WorkloadRecord,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        sdk_workload = self._load_sdk_workload(extension, workload)
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        artifact_root = self._artifact_root(extension.extension_id, workload.workload_id, input_digest, input_config)
        artifact_root.mkdir(parents=True, exist_ok=True)
        capability_registry = self._build_sdk_capability_registry(
            workspace=workspace, artifact_root=artifact_root, input_config=input_config
        )
        missing_capabilities = capability_registry.preflight(list(workload.required_capabilities))
        if missing_capabilities:
            raise ValueError("E_SDK_CAPABILITY_MISSING: " + ", ".join(missing_capabilities))

        ctx = SDKWorkloadContext(
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

        if interaction_context is not None:
            await interaction_context.emit_event(
                StreamEventType.MODEL_SELECTED,
                {"model_id": "extension-sdk-v0", "reason": "sdk_workload_run", "authoritative": False},
            )
            await interaction_context.emit_event(
                StreamEventType.MODEL_LOADING,
                {"cold_start": False, "progress": 1.0, "authoritative": False},
            )
            await interaction_context.emit_event(
                StreamEventType.MODEL_READY,
                {"model_id": "extension-sdk-v0", "warm_state": "warm", "load_ms": 0, "authoritative": False},
            )

        result = run_sdk_workload(sdk_workload, ctx, dict(input_config))
        self._validate_sdk_artifacts(result, artifact_root)

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
                StreamEventType.TURN_FINAL,
                {"authoritative": False, "summary": summary},
            )
            await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload.workload_id))

        artifact_manifest = self._build_artifact_manifest(artifact_root)
        manifest_path = artifact_root / "artifact_manifest.json"
        manifest_path.write_text(json.dumps(artifact_manifest, indent=2, sort_keys=True), encoding="utf-8")

        provenance = self._build_sdk_provenance(
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

    def _load_catalog_payload(self) -> dict[str, Any]:
        if not self.catalog_path.exists():
            return {"extensions": []}
        data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"extensions": []}
        extensions = data.get("extensions", [])
        if not isinstance(extensions, list):
            return {"extensions": []}
        return {"extensions": extensions}

    def _save_catalog_payload(self, payload: dict[str, Any]) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _load_manifest(self, repo_path: Path) -> _LoadedManifest:
        legacy_manifest_path = repo_path / LEGACY_MANIFEST_FILENAME
        if legacy_manifest_path.exists():
            manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError(f"{LEGACY_MANIFEST_FILENAME} must be a JSON object")
            return _LoadedManifest(
                payload=manifest,
                manifest_path=legacy_manifest_path,
                contract_style=CONTRACT_STYLE_LEGACY,
            )

        for filename in SDK_MANIFEST_FILENAMES:
            sdk_manifest_path = repo_path / filename
            if not sdk_manifest_path.exists():
                continue
            manifest_model = load_sdk_manifest(sdk_manifest_path)
            return _LoadedManifest(
                payload=manifest_model.model_dump(mode="json"),
                manifest_path=sdk_manifest_path,
                contract_style=CONTRACT_STYLE_SDK_V0,
            )

        expected = [LEGACY_MANIFEST_FILENAME, *SDK_MANIFEST_FILENAMES]
        raise FileNotFoundError(f"Missing extension manifest in repo: {repo_path} (expected one of {expected})")

    def _record_from_manifest(
        self,
        manifest: dict[str, Any],
        *,
        source: str,
        path: Path,
        contract_style: str,
        manifest_path: Path,
    ) -> ExtensionRecord:
        if contract_style == CONTRACT_STYLE_SDK_V0:
            return self._sdk_record_from_manifest(manifest, source=source, path=path, manifest_path=manifest_path)
        return self._legacy_record_from_manifest(manifest, source=source, path=path, manifest_path=manifest_path)

    def _legacy_record_from_manifest(
        self, manifest: dict[str, Any], *, source: str, path: Path, manifest_path: Path
    ) -> ExtensionRecord:
        extension_id = str(manifest.get("extension_id", "")).strip()
        extension_version = str(manifest.get("extension_version", "")).strip()
        extension_api_version = str(manifest.get("extension_api_version", "")).strip() or "1.0.0"
        module = str(manifest.get("module", "")).strip()
        register_callable = str(manifest.get("register_callable", "")).strip() or "register"
        if not extension_id:
            raise ValueError("extension_id is required in manifest")
        if not extension_version:
            raise ValueError("extension_version is required in manifest")
        if not module:
            raise ValueError("module is required in manifest")

        workloads: list[WorkloadRecord] = []
        for item in manifest.get("workloads", []):
            workload_id = str(item.get("workload_id", "")).strip()
            workload_version = str(item.get("workload_version", "")).strip() or "0.0.0"
            if workload_id:
                workloads.append(
                    WorkloadRecord(
                        workload_id=workload_id,
                        workload_version=workload_version,
                        contract_style=CONTRACT_STYLE_LEGACY,
                    )
                )

        return ExtensionRecord(
            extension_id=extension_id,
            extension_version=extension_version,
            source=source,
            extension_api_version=extension_api_version,
            path=str(path),
            module=module,
            register_callable=register_callable,
            workloads=tuple(workloads),
            contract_style=CONTRACT_STYLE_LEGACY,
            manifest_path=str(manifest_path),
        )

    def _sdk_record_from_manifest(
        self, manifest: dict[str, Any], *, source: str, path: Path, manifest_path: Path
    ) -> ExtensionRecord:
        extension_id = str(manifest.get("extension_id", "")).strip()
        extension_version = str(manifest.get("extension_version", "")).strip()
        manifest_version = str(manifest.get("manifest_version", "")).strip() or "v0"
        if not extension_id:
            raise ValueError("extension_id is required in manifest")
        if not extension_version:
            raise ValueError("extension_version is required in manifest")

        workloads: list[WorkloadRecord] = []
        for item in manifest.get("workloads", []):
            workload_id = str(item.get("workload_id", "")).strip()
            if not workload_id:
                continue
            required_capabilities = tuple(
                str(cap).strip() for cap in item.get("required_capabilities", []) if str(cap).strip()
            )
            workloads.append(
                WorkloadRecord(
                    workload_id=workload_id,
                    workload_version=extension_version,
                    entrypoint=str(item.get("entrypoint", "")).strip(),
                    required_capabilities=required_capabilities,
                    contract_style=CONTRACT_STYLE_SDK_V0,
                )
            )

        return ExtensionRecord(
            extension_id=extension_id,
            extension_version=extension_version,
            source=source,
            extension_api_version=manifest_version,
            path=str(path),
            module="",
            register_callable="",
            workloads=tuple(workloads),
            contract_style=CONTRACT_STYLE_SDK_V0,
            manifest_path=str(manifest_path),
        )

    def _row_from_record(self, record: ExtensionRecord) -> dict[str, Any]:
        return {
            "extension_id": record.extension_id,
            "extension_version": record.extension_version,
            "extension_api_version": record.extension_api_version,
            "source": record.source,
            "path": record.path,
            "module": record.module,
            "register_callable": record.register_callable,
            "contract_style": record.contract_style,
            "manifest_path": record.manifest_path,
            "workloads": [
                {
                    "workload_id": w.workload_id,
                    "workload_version": w.workload_version,
                    "entrypoint": w.entrypoint,
                    "required_capabilities": list(w.required_capabilities),
                    "contract_style": w.contract_style,
                }
                for w in record.workloads
            ],
        }

    def _load_legacy_workload(self, extension: ExtensionRecord, workload_id: str) -> Workload:
        extension_path = Path(extension.path).resolve()
        if not extension_path.exists():
            raise FileNotFoundError(f"Extension path missing: {extension.path}")
        module_name = extension.module
        register_name = extension.register_callable
        self._validate_extension_imports(extension_path, module_name)

        added_path = False
        if str(extension_path) not in sys.path:
            sys.path.insert(0, str(extension_path))
            added_path = True
        try:
            module = importlib.import_module(module_name)
            register = getattr(module, register_name, None)
            if register is None or not callable(register):
                raise ValueError(f"Register callable '{register_name}' not found in module '{module_name}'")
            registry = _WorkloadRegistry()
            register(registry)
            workloads = registry.workloads()
            workload = workloads.get(workload_id)
            if workload is None:
                raise ValueError(f"Extension '{extension.extension_id}' does not register workload '{workload_id}'")
            return workload
        finally:
            if added_path:
                try:
                    sys.path.remove(str(extension_path))
                except ValueError:
                    pass

    def _load_sdk_workload(self, extension: ExtensionRecord, workload: WorkloadRecord) -> SDKWorkload:
        extension_path = Path(extension.path).resolve()
        if not extension_path.exists():
            raise FileNotFoundError(f"Extension path missing: {extension.path}")
        module_name, attr_name = self._parse_sdk_entrypoint(workload.entrypoint)
        self._validate_extension_imports(extension_path, module_name)

        added_path = False
        if str(extension_path) not in sys.path:
            sys.path.insert(0, str(extension_path))
            added_path = True
        try:
            module = importlib.import_module(module_name)
            target = getattr(module, attr_name, None)
            if target is None:
                raise ValueError(f"E_SDK_ENTRYPOINT_MISSING: {workload.entrypoint}")
            if inspect.isclass(target):
                instance = target()
            elif callable(target) and hasattr(target, "run"):
                instance = target
            elif callable(target):

                class _CallableWorkload:
                    def __init__(self, func):
                        self._func = func

                    def run(self, ctx: SDKWorkloadContext, payload: dict[str, Any]) -> WorkloadResult:
                        return self._func(ctx, payload)

                instance = _CallableWorkload(target)
            else:
                raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {workload.entrypoint}")

            run_method = getattr(instance, "run", None)
            if run_method is None or not callable(run_method):
                raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {workload.entrypoint}")
            return instance
        finally:
            if added_path:
                try:
                    sys.path.remove(str(extension_path))
                except ValueError:
                    pass

    def _parse_sdk_entrypoint(self, entrypoint: str) -> tuple[str, str]:
        value = str(entrypoint or "").strip()
        module_name, sep, attr_name = value.partition(":")
        if sep != ":" or not module_name.strip() or not attr_name.strip():
            raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {entrypoint}")
        return module_name.strip(), attr_name.strip()

    def _validate_extension_imports(self, extension_path: Path, module_name: str) -> None:
        module_path = extension_path / Path(*module_name.split("."))
        file_path = module_path.with_suffix(".py")
        package_init_path = module_path / "__init__.py"
        if file_path.exists():
            source_path = file_path
        elif package_init_path.exists():
            source_path = package_init_path
        else:
            raise FileNotFoundError(f"Extension module source not found for '{module_name}' under {extension_path}")

        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        blocked_prefixes = (
            "orket.orchestration",
            "orket.decision_nodes",
            "orket.runtime",
            "orket.application",
            "orket.adapters",
            "orket.interfaces",
            "orket.services",
            "orket.kernel",
            "orket.core",
            "orket.webhook_server",
            "orket.orket",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = str(alias.name or "")
                    if name.startswith("orket.") and not name.startswith("orket.extensions"):
                        if any(name.startswith(prefix) for prefix in blocked_prefixes):
                            raise ValueError(f"Extension import blocked by isolation policy: {name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module.startswith("orket.") and not module.startswith("orket.extensions"):
                    if any(module.startswith(prefix) for prefix in blocked_prefixes):
                        raise ValueError(f"Extension import blocked by isolation policy: {module}")

    def _build_sdk_capability_registry(
        self, *, workspace: Path, artifact_root: Path, input_config: dict[str, Any]
    ) -> CapabilityRegistry:
        registry = CapabilityRegistry()
        registry.register("workspace.root", str(workspace))
        registry.register("artifact.root", str(artifact_root))
        configured = input_config.get("capabilities")
        if isinstance(configured, dict):
            items = sorted((str(k).strip(), v) for k, v in configured.items())
            for capability_id, provider in items:
                if not capability_id or registry.has(capability_id):
                    continue
                registry.register(capability_id, provider)
        return registry

    def _validate_sdk_artifacts(self, result: WorkloadResult, artifact_root: Path) -> None:
        artifact_root_resolved = artifact_root.resolve()
        for artifact in result.artifacts:
            artifact_path = str(artifact.path).strip()
            if not artifact_path:
                raise ValueError("E_SDK_ARTIFACT_PATH_INVALID")
            target = (artifact_root / artifact_path).resolve()
            if not str(target).startswith(str(artifact_root_resolved)):
                raise ValueError(f"E_SDK_ARTIFACT_ESCAPE: {artifact_path}")
            if not target.exists() or not target.is_file():
                raise FileNotFoundError(f"E_SDK_ARTIFACT_MISSING: {artifact_path}")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != artifact.digest_sha256:
                raise ValueError(f"E_SDK_ARTIFACT_DIGEST_MISMATCH: {artifact_path}")

    def _artifact_root(
        self,
        extension_id: str,
        workload_id: str,
        plan_hash: str,
        input_config: dict[str, Any],
    ) -> Path:
        seed_raw = str(input_config.get("seed", "none"))
        seed_slug = seed_raw.replace("/", "_").replace("\\", "_")
        leaf = f"{workload_id}-{seed_slug}-{plan_hash[:12]}"
        return self.project_root / "workspace" / "extensions" / extension_id / leaf

    def _reliable_mode_enabled(self) -> bool:
        raw = (os.getenv(RELIABLE_MODE_ENV, "true") or "").strip().lower()
        return raw not in {"0", "false", "no", "off"}

    def _validate_required_materials(self, materials: Any) -> None:
        missing: list[str] = []
        for material in list(materials or []):
            rel = str(material or "").strip()
            if not rel:
                continue
            target = (self.project_root / rel).resolve()
            if not str(target).startswith(str(self.project_root)):
                raise ValueError(f"Material path escapes project root: {rel}")
            if not target.exists():
                missing.append(rel)
        if missing:
            raise FileNotFoundError("Required materials missing: " + ", ".join(sorted(missing)))

    def _validate_clean_git_if_required(self) -> None:
        raw = (os.getenv(RELIABLE_REQUIRE_CLEAN_GIT_ENV, "false") or "").strip().lower()
        if raw not in {"1", "true", "yes", "on"}:
            return
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0:
            raise RuntimeError("Unable to validate git clean state")
        if status.stdout.strip():
            raise RuntimeError("Reliable Mode requires clean git state")

    def _run_validators(self, workload: Workload, run_result: dict[str, Any], artifact_root: Path) -> list[str]:
        errors: list[str] = []
        for validator in list(workload.validators() or []):
            for error in list(validator(run_result, str(artifact_root)) or []):
                msg = str(error or "").strip()
                if msg:
                    errors.append(msg)
        return errors

    def _build_provenance(
        self,
        *,
        extension: ExtensionRecord,
        workload: Workload,
        input_config: dict[str, Any],
        run_plan: RunPlan,
        plan_hash: str,
        run_result: dict[str, Any],
        summary: dict[str, Any],
        artifact_manifest: dict[str, Any],
        artifact_root: Path,
    ) -> dict[str, Any]:
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "reliable_mode": self._reliable_mode_enabled(),
            "extension": {
                "extension_id": extension.extension_id,
                "extension_version": extension.extension_version,
                "extension_api_version": extension.extension_api_version,
                "source": extension.source,
            },
            "workload": {
                "workload_id": workload.workload_id,
                "workload_version": workload.workload_version,
            },
            "input_config": input_config,
            "input_config_digest": input_digest,
            "run_plan": run_plan.canonical_payload(),
            "plan_hash": plan_hash,
            "run_result": run_result,
            "summary": summary,
            "artifact_manifest": artifact_manifest,
            "artifact_root": str(artifact_root),
        }

    def _build_sdk_provenance(
        self,
        *,
        extension: ExtensionRecord,
        workload: WorkloadRecord,
        input_config: dict[str, Any],
        input_digest: str,
        run_result: dict[str, Any],
        summary: dict[str, Any],
        artifact_manifest: dict[str, Any],
        artifact_root: Path,
        department: str,
    ) -> dict[str, Any]:
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "reliable_mode": self._reliable_mode_enabled(),
            "contract_style": CONTRACT_STYLE_SDK_V0,
            "extension": {
                "extension_id": extension.extension_id,
                "extension_version": extension.extension_version,
                "manifest_path": extension.manifest_path,
                "source": extension.source,
            },
            "workload": {
                "workload_id": workload.workload_id,
                "workload_version": workload.workload_version,
                "entrypoint": workload.entrypoint,
                "required_capabilities": list(workload.required_capabilities),
            },
            "department": department,
            "input_config": input_config,
            "input_config_digest": input_digest,
            "run_result": run_result,
            "summary": summary,
            "artifact_manifest": artifact_manifest,
            "artifact_root": str(artifact_root),
        }

    def _build_artifact_manifest(self, artifact_root: Path) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        for path in sorted(artifact_root.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(artifact_root)).replace("\\", "/")
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append({"path": rel, "sha256": file_hash})
        digest = hashlib.sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {"files": files, "manifest_sha256": digest}

    def _run_command(self, command: list[str], *, cwd: Path) -> None:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(command)}\nstdout={result.stdout.strip()}\nstderr={result.stderr.strip()}"
            )

    def _discover_entry_point_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            group = entry_points().select(group="orket.extensions")
        except Exception:
            return rows

        for ep in group:
            try:
                loader = ep.load()
                if not callable(loader):
                    continue
                descriptor = loader()
                if not isinstance(descriptor, dict):
                    continue
                if "source" not in descriptor:
                    descriptor["source"] = f"entrypoint:{ep.name}"
                if "register_callable" not in descriptor:
                    descriptor["register_callable"] = "register"
                rows.append(descriptor)
            except Exception:
                continue
        return rows
