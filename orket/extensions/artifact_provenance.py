from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from posixpath import normpath
from typing import Any

from orket_extension_sdk.result import WorkloadResult

from .contracts import RunPlan, Workload
from .governed_identity import (
    EXTENSION_WORKLOAD_OPERATOR_SURFACE_MANIFEST,
    EXTENSION_WORKLOAD_OPERATOR_SURFACE_PROVENANCE,
    build_base_provenance_payload,
    build_extension_governed_identity,
    validate_governed_identity,
)
from .models import CONTRACT_STYLE_SDK_V0, ExtensionRecord, WorkloadRecord
from .reproducibility import ReproducibilityEnforcer


class ArtifactProvenanceBuilder:
    _ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    _ARTIFACT_FILE_SIZE_CAP_BYTES_ENV = "ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES"
    _ARTIFACT_TOTAL_SIZE_CAP_BYTES_ENV = "ORKET_EXT_ARTIFACT_TOTAL_SIZE_CAP_BYTES"
    _ARTIFACT_FILE_SIZE_CAP_BYTES_DEFAULT = 32 * 1024 * 1024
    _ARTIFACT_TOTAL_SIZE_CAP_BYTES_DEFAULT = 128 * 1024 * 1024

    def __init__(self, project_root: Path, reproducibility: ReproducibilityEnforcer) -> None:
        self.project_root = project_root
        self.reproducibility = reproducibility

    def artifact_root(
        self,
        extension_id: str,
        workload_id: str,
        plan_hash: str,
        input_config: dict[str, Any],
    ) -> Path:
        extension_id = self._validated_id(extension_id, code="E_EXT_ID_INVALID")
        workload_id = self._validated_id(workload_id, code="E_WORKLOAD_ID_INVALID")
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

    def validate_sdk_artifacts(self, result: WorkloadResult, artifact_root: Path) -> None:
        artifact_root_resolved = artifact_root.resolve()
        max_file_bytes = self._artifact_file_size_cap_bytes()
        max_total_bytes = self._artifact_total_size_cap_bytes()
        total_bytes = 0
        failures: list[dict[str, str]] = []
        artifacts = sorted(
            (artifact for artifact in result.artifacts),
            key=lambda artifact: str(artifact.path).replace("\\", "/"),
        )
        for artifact in artifacts:
            artifact_path = str(artifact.path).strip().replace("\\", "/")
            if not artifact_path:
                failures.append(self._failure(path_norm="", code="E_SDK_ARTIFACT_PATH_INVALID", detail="empty"))
                continue
            if Path(artifact_path).is_absolute():
                failures.append(self._failure(path_norm=artifact_path, code="E_ARTIFACT_PATH_ABSOLUTE", detail=artifact_path))
                continue
            if ".." in Path(artifact_path).parts:
                failures.append(self._failure(path_norm=artifact_path, code="E_ARTIFACT_PATH_TRAVERSAL", detail=artifact_path))
                continue
            target_path = artifact_root / artifact_path
            if target_path.is_symlink():
                failures.append(
                    self._failure(path_norm=artifact_path, code="E_ARTIFACT_SYMLINK_FORBIDDEN", detail=artifact_path)
                )
                continue
            target = target_path.resolve()
            try:
                target.relative_to(artifact_root_resolved)
            except ValueError:
                failures.append(self._failure(path_norm=artifact_path, code="E_ARTIFACT_PATH_ESCAPE", detail=artifact_path))
                continue
            if not target.exists() or not target.is_file():
                failures.append(self._failure(path_norm=artifact_path, code="E_SDK_ARTIFACT_MISSING", detail=artifact_path))
                continue
            file_size = target.stat().st_size
            if file_size > max_file_bytes:
                failures.append(
                    self._failure(path_norm=artifact_path, code="E_ARTIFACT_FILE_SIZE_CAP", detail=f"size={file_size} cap={max_file_bytes}")
                )
                continue
            total_bytes += file_size
            if total_bytes > max_total_bytes:
                failures.append(
                    self._failure(path_norm=artifact_path, code="E_ARTIFACT_TOTAL_SIZE_CAP", detail=f"total={total_bytes} cap={max_total_bytes}")
                )
                continue
            if self._stream_sha256(target) != artifact.digest_sha256:
                failures.append(
                    self._failure(path_norm=artifact_path, code="E_SDK_ARTIFACT_DIGEST_MISMATCH", detail=artifact_path)
                )
        if failures:
            raise ValueError(self._canonical_failure_payload(failures))

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
        department: str,
    ) -> dict[str, Any]:
        input_digest = hashlib.sha256(
            json.dumps(input_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        verbose = self._provenance_verbose_enabled()
        governed_identity = build_extension_governed_identity(
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint="",
            required_capabilities=[],
            contract_style=extension.contract_style,
            department=department,
            input_identity=plan_hash,
            operator_surface=EXTENSION_WORKLOAD_OPERATOR_SURFACE_PROVENANCE,
            reliable_mode_enabled=self.reproducibility.reliable_mode_enabled(),
            reliable_require_clean_git=self._reliable_require_clean_git_enabled(),
            provenance_verbose_enabled=verbose,
            artifact_file_size_cap_bytes=self._artifact_file_size_cap_bytes(),
            artifact_total_size_cap_bytes=self._artifact_total_size_cap_bytes(),
        )
        return {
            **build_base_provenance_payload(
                extension=extension,
                governed_identity=governed_identity,
                artifact_manifest_hash=self._prefixed_manifest_hash(artifact_manifest),
                artifact_root=str(artifact_root),
                reliable_mode_enabled=self.reproducibility.reliable_mode_enabled(),
            ),
            "extension": {
                "extension_id": extension.extension_id,
                "extension_version": extension.extension_version,
                "extension_api_version": extension.extension_api_version,
                "source": extension.source,
                "source_ref": extension.source_ref,
                "resolved_commit_sha": extension.resolved_commit_sha,
                "manifest_digest_sha256": extension.manifest_digest_sha256,
                "security_mode": extension.security_mode,
                "security_profile": extension.security_profile,
                "security_policy_version": extension.security_policy_version,
                "compat_fallbacks": list(extension.compat_fallbacks),
            },
            "workload": {"workload_id": workload.workload_id, "workload_version": workload.workload_version},
            "input_config": input_config if verbose else {},
            "input_config_digest": input_digest,
            "input_config_redacted": self._redacted_snapshot(input_config),
            "run_plan": run_plan.canonical_payload(),
            "plan_hash": plan_hash,
            "run_result": run_result if verbose else {},
            "run_result_redacted": self._redacted_snapshot(run_result),
            "summary": summary if verbose else {},
            "summary_redacted": self._redacted_snapshot(summary),
            "artifact_manifest": artifact_manifest,
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
        verbose = self._provenance_verbose_enabled()
        governed_identity = build_extension_governed_identity(
            extension=extension,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            workload_entrypoint=workload.entrypoint,
            required_capabilities=list(workload.required_capabilities),
            contract_style=workload.contract_style or extension.contract_style,
            department=department,
            input_identity=input_digest,
            operator_surface=EXTENSION_WORKLOAD_OPERATOR_SURFACE_PROVENANCE,
            reliable_mode_enabled=self.reproducibility.reliable_mode_enabled(),
            reliable_require_clean_git=self._reliable_require_clean_git_enabled(),
            provenance_verbose_enabled=verbose,
            artifact_file_size_cap_bytes=self._artifact_file_size_cap_bytes(),
            artifact_total_size_cap_bytes=self._artifact_total_size_cap_bytes(),
        )
        return {
            **build_base_provenance_payload(
                extension=extension,
                governed_identity=governed_identity,
                artifact_manifest_hash=self._prefixed_manifest_hash(artifact_manifest),
                artifact_root=str(artifact_root),
                reliable_mode_enabled=self.reproducibility.reliable_mode_enabled(),
            ),
            "contract_style": CONTRACT_STYLE_SDK_V0,
            "extension": {
                "extension_id": extension.extension_id,
                "extension_version": extension.extension_version,
                "manifest_path": extension.manifest_path,
                "source": extension.source,
                "source_ref": extension.source_ref,
                "resolved_commit_sha": extension.resolved_commit_sha,
                "manifest_digest_sha256": extension.manifest_digest_sha256,
                "security_mode": extension.security_mode,
                "security_profile": extension.security_profile,
                "security_policy_version": extension.security_policy_version,
                "compat_fallbacks": list(extension.compat_fallbacks),
            },
            "workload": {
                "workload_id": workload.workload_id,
                "workload_version": workload.workload_version,
                "entrypoint": workload.entrypoint,
                "required_capabilities": list(workload.required_capabilities),
            },
            "department": department,
            "input_config": input_config if verbose else {},
            "input_config_digest": input_digest,
            "plan_hash": input_digest,
            "input_config_redacted": self._redacted_snapshot(input_config),
            "run_result": run_result if verbose else {},
            "run_result_redacted": self._redacted_snapshot(run_result),
            "summary": summary if verbose else {},
            "summary_redacted": self._redacted_snapshot(summary),
            "artifact_manifest": artifact_manifest,
        }

    def build_artifact_manifest(
        self,
        artifact_root: Path,
        *,
        plan_hash: str = "",
        governed_identity: dict[str, Any] | None = None,
        provenance_ref: str = "provenance.json",
    ) -> dict[str, Any]:
        artifact_root_resolved = artifact_root.resolve()
        max_file_bytes = self._artifact_file_size_cap_bytes()
        max_total_bytes = self._artifact_total_size_cap_bytes()
        total_bytes = 0
        files: list[dict[str, Any]] = []
        for path in sorted(artifact_root.rglob("*"), key=lambda entry: entry.as_posix()):
            if not path.is_file():
                continue
            rel = str(path.relative_to(artifact_root)).replace("\\", "/")
            if path.is_symlink():
                raise ValueError(f"E_ARTIFACT_SYMLINK_FORBIDDEN: {rel}")
            resolved = path.resolve()
            try:
                resolved.relative_to(artifact_root_resolved)
            except ValueError:
                raise ValueError(f"E_ARTIFACT_PATH_ESCAPE: {rel}") from None
            file_size = resolved.stat().st_size
            if file_size > max_file_bytes:
                raise ValueError(f"E_ARTIFACT_FILE_SIZE_CAP: {rel}")
            total_bytes += file_size
            if total_bytes > max_total_bytes:
                raise ValueError(f"E_ARTIFACT_TOTAL_SIZE_CAP: {rel}")
            files.append({"path": rel, "sha256": self._stream_sha256(resolved)})
        manifest = {
            "files": files,
            "manifest_sha256": hashlib.sha256(
                json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
        if governed_identity is None:
            return manifest
        validate_governed_identity(governed_identity)
        manifest.update(
            {
                "claim_tier": governed_identity["claim_tier"],
                "compare_scope": governed_identity["compare_scope"],
                "operator_surface": EXTENSION_WORKLOAD_OPERATOR_SURFACE_MANIFEST,
                "policy_digest": governed_identity["policy_digest"],
                "control_bundle_hash": governed_identity["control_bundle_hash"],
                "determinism_class": governed_identity["determinism_class"],
                "plan_hash": str(plan_hash or "").strip(),
                "provenance_ref": str(provenance_ref or "").strip(),
            }
        )
        return manifest

    @classmethod
    def _validated_id(cls, value: str, *, code: str) -> str:
        cleaned = str(value or "").strip()
        if not cls._ID_PATTERN.fullmatch(cleaned):
            raise ValueError(f"{code}: {value}")
        return cleaned

    @staticmethod
    def _stream_sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def _artifact_file_size_cap_bytes(cls) -> int:
        raw = str(os.getenv(cls._ARTIFACT_FILE_SIZE_CAP_BYTES_ENV, "")).strip()
        return max(1, int(raw)) if raw else cls._ARTIFACT_FILE_SIZE_CAP_BYTES_DEFAULT

    @classmethod
    def _artifact_total_size_cap_bytes(cls) -> int:
        raw = str(os.getenv(cls._ARTIFACT_TOTAL_SIZE_CAP_BYTES_ENV, "")).strip()
        return max(1, int(raw)) if raw else cls._ARTIFACT_TOTAL_SIZE_CAP_BYTES_DEFAULT

    @staticmethod
    def _reliable_require_clean_git_enabled() -> bool:
        raw = str(os.getenv("ORKET_RELIABLE_REQUIRE_CLEAN_GIT", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _provenance_verbose_enabled() -> bool:
        raw = str(os.getenv("ORKET_EXT_PROVENANCE_VERBOSE", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _redacted_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
        keys = sorted(str(key) for key in payload.keys())
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {"keys": keys, "item_count": len(keys), "payload_digest_sha256": digest}

    @staticmethod
    def _failure(*, path_norm: str, code: str, detail: str) -> dict[str, str]:
        normalized_path = normpath(path_norm.replace("\\", "/")) if path_norm else ""
        normalized_detail = str(detail).strip()
        return {
            "path_norm": normalized_path,
            "code": code,
            "detail": normalized_detail,
            "detail_digest": hashlib.sha256(normalized_detail.encode("utf-8")).hexdigest(),
        }

    @staticmethod
    def _canonical_failure_payload(failures: list[dict[str, str]]) -> str:
        ordered = sorted(failures, key=lambda row: (row["path_norm"], row["code"], row["detail_digest"]))
        return "E_SDK_ARTIFACT_VALIDATION_FAILED: " + json.dumps(
            {"errors": ordered},
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _prefixed_manifest_hash(artifact_manifest: dict[str, Any]) -> str:
        manifest_sha256 = str(artifact_manifest.get("manifest_sha256") or "").strip()
        if not manifest_sha256:
            raise ValueError("E_ARTIFACT_MANIFEST_HASH_MISSING")
        return f"sha256:{manifest_sha256}"
