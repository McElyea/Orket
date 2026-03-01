from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.result import WorkloadResult

from .contracts import RunPlan, Workload
from .models import CONTRACT_STYLE_SDK_V0, ExtensionRecord, WorkloadRecord
from .reproducibility import ReproducibilityEnforcer


class WorkloadArtifacts:
    """Artifact, capability, and provenance helpers for extension runs."""

    def __init__(self, project_root: Path, reproducibility: ReproducibilityEnforcer) -> None:
        self.project_root = project_root
        self.reproducibility = reproducibility

    @staticmethod
    def build_sdk_capability_registry(
        *,
        workspace: Path,
        artifact_root: Path,
        input_config: dict[str, Any],
    ) -> CapabilityRegistry:
        registry = CapabilityRegistry()
        registry.register("workspace.root", str(workspace))
        registry.register("artifact.root", str(artifact_root))
        configured = input_config.get("capabilities")
        if isinstance(configured, dict):
            items = sorted((str(key).strip(), value) for key, value in configured.items())
            for capability_id, provider in items:
                if not capability_id or registry.has(capability_id):
                    continue
                registry.register(capability_id, provider)
        return registry

    @staticmethod
    def validate_sdk_artifacts(result: WorkloadResult, artifact_root: Path) -> None:
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

    def artifact_root(
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

    @staticmethod
    def run_validators(workload: Workload, run_result: dict[str, Any], artifact_root: Path) -> list[str]:
        errors: list[str] = []
        for validator in list(workload.validators() or []):
            for error in list(validator(run_result, str(artifact_root)) or []):
                msg = str(error or "").strip()
                if msg:
                    errors.append(msg)
        return errors

    def build_provenance(
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
            "reliable_mode": self.reproducibility.reliable_mode_enabled(),
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

    def build_sdk_provenance(
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
            "reliable_mode": self.reproducibility.reliable_mode_enabled(),
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

    @staticmethod
    def build_artifact_manifest(artifact_root: Path) -> dict[str, Any]:
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
