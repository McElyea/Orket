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

from orket.runtime_paths import durable_root

from .contracts import ExtensionRegistry, RunPlan, Workload
from .runtime import ExtensionEngineAdapter, RunContext
from orket.streaming.contracts import CommitIntent, StreamEventType

RELIABLE_MODE_ENV = "ORKET_RELIABLE_MODE"
RELIABLE_REQUIRE_CLEAN_GIT_ENV = "ORKET_RELIABLE_REQUIRE_CLEAN_GIT"
MANIFEST_FILENAME = "orket_extension.json"


def default_extensions_catalog_path() -> Path:
    env_path = (os.getenv("ORKET_EXTENSIONS_CATALOG") or "").strip()
    if env_path:
        return Path(env_path)
    return durable_root() / "config" / "extensions_catalog.json"


@dataclass(frozen=True)
class WorkloadRecord:
    workload_id: str
    workload_version: str


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
            if not extension_id or extension_id in seen_ids:
                continue
            seen_ids.add(extension_id)

            workloads: list[WorkloadRecord] = []
            for item in row.get("workloads", []):
                workload_id = str(item.get("workload_id", "")).strip()
                if not workload_id:
                    continue
                workloads.append(
                    WorkloadRecord(
                        workload_id=workload_id,
                        workload_version=str(item.get("workload_version", "")).strip() or "0.0.0",
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

        manifest = self._load_manifest(destination)
        record = self._record_from_manifest(manifest, source=repo_value, path=destination)
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
        extension, _ = resolved
        workload = self._load_workload(extension, workload_id)
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

    def _load_manifest(self, repo_path: Path) -> dict[str, Any]:
        manifest_path = repo_path / MANIFEST_FILENAME
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing {MANIFEST_FILENAME} in extension repo: {repo_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError(f"{MANIFEST_FILENAME} must be a JSON object")
        return manifest

    def _record_from_manifest(self, manifest: dict[str, Any], *, source: str, path: Path) -> ExtensionRecord:
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
                workloads.append(WorkloadRecord(workload_id=workload_id, workload_version=workload_version))

        return ExtensionRecord(
            extension_id=extension_id,
            extension_version=extension_version,
            source=source,
            extension_api_version=extension_api_version,
            path=str(path),
            module=module,
            register_callable=register_callable,
            workloads=tuple(workloads),
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
            "workloads": [
                {"workload_id": w.workload_id, "workload_version": w.workload_version} for w in record.workloads
            ],
        }

    def _load_workload(self, extension: ExtensionRecord, workload_id: str) -> Workload:
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
