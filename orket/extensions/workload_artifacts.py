from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from posixpath import normpath
from typing import Any

from orket.capabilities.audio_player import build_audio_player
from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket.capabilities.tts_piper import build_tts_provider
from orket.services.scoped_memory_store import MemoryControls
from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.audio import NullAudioPlayer
from orket_extension_sdk.result import WorkloadResult

from .contracts import RunPlan, Workload
from .models import CONTRACT_STYLE_SDK_V0, ExtensionRecord, WorkloadRecord
from .reproducibility import ReproducibilityEnforcer


class WorkloadArtifacts:
    """Artifact, capability, and provenance helpers for extension runs."""

    _ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    _ARTIFACT_FILE_SIZE_CAP_BYTES_ENV = "ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES"
    _ARTIFACT_TOTAL_SIZE_CAP_BYTES_ENV = "ORKET_EXT_ARTIFACT_TOTAL_SIZE_CAP_BYTES"
    _ARTIFACT_FILE_SIZE_CAP_BYTES_DEFAULT = 32 * 1024 * 1024
    _ARTIFACT_TOTAL_SIZE_CAP_BYTES_DEFAULT = 128 * 1024 * 1024

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
        if not registry.has("tts.speak"):
            registry.register("tts.speak", build_tts_provider(input_config=input_config))
        if not registry.has("audio.play"):
            registry.register("audio.play", build_audio_player(input_config=input_config))
        if not registry.has("model.generate"):
            requested_model = str(input_config.get("model") or input_config.get("model_id") or "").strip()
            model = requested_model or "qwen2.5-coder:7b"
            raw_temperature = input_config.get("temperature", 0.2)
            try:
                temperature = float(raw_temperature)
            except (TypeError, ValueError):
                temperature = 0.2
            raw_seed = input_config.get("seed")
            try:
                seed = int(raw_seed) if raw_seed is not None else None
            except (TypeError, ValueError):
                seed = None
            registry.register(
                "model.generate",
                LocalModelCapabilityProvider(
                    model=model,
                    temperature=temperature,
                    seed=seed,
                ),
            )
        if not registry.has("memory.write") or not registry.has("memory.query"):
            memory_settings = input_config.get("memory")
            if not isinstance(memory_settings, dict):
                memory_settings = {}
            controls = MemoryControls(
                session_memory_enabled=WorkloadArtifacts._resolve_bool_setting(
                    memory_settings.get("session_memory_enabled", input_config.get("session_memory_enabled", True))
                ),
                profile_memory_enabled=WorkloadArtifacts._resolve_bool_setting(
                    memory_settings.get("profile_memory_enabled", input_config.get("profile_memory_enabled", True))
                ),
            )
            memory_provider = SQLiteMemoryCapabilityProvider(
                db_path=(workspace / ".orket" / "durable" / "db" / "extension_memory.db"),
                controls=controls,
            )
            if not registry.has("memory.write"):
                registry.register("memory.write", memory_provider)
            if not registry.has("memory.query"):
                registry.register("memory.query", memory_provider)
        if not registry.has("speech.transcribe"):
            registry.register("speech.transcribe", HostSTTCapabilityProvider())
        if not registry.has("voice.turn_control"):
            voice_settings = input_config.get("voice")
            if not isinstance(voice_settings, dict):
                voice_settings = {}
            registry.register(
                "voice.turn_control",
                HostVoiceTurnController(
                    default_silence_delay_seconds=WorkloadArtifacts._resolve_float_setting(
                        voice_settings.get("silence_delay_sec", input_config.get("silence_delay_sec", 2.0)),
                        default=2.0,
                    ),
                    min_silence_delay_seconds=WorkloadArtifacts._resolve_float_setting(
                        voice_settings.get("silence_delay_min_sec", input_config.get("silence_delay_min_sec", 0.2)),
                        default=0.2,
                    ),
                    max_silence_delay_seconds=WorkloadArtifacts._resolve_float_setting(
                        voice_settings.get("silence_delay_max_sec", input_config.get("silence_delay_max_sec", 10.0)),
                        default=10.0,
                    ),
                ),
            )
        if not registry.has("speech.play_clip"):
            registry.register("speech.play_clip", NullAudioPlayer())
        return registry

    @staticmethod
    def validate_sdk_artifacts(result: WorkloadResult, artifact_root: Path) -> None:
        artifact_root_resolved = artifact_root.resolve()
        max_file_bytes = WorkloadArtifacts._artifact_file_size_cap_bytes()
        max_total_bytes = WorkloadArtifacts._artifact_total_size_cap_bytes()
        total_bytes = 0
        failures: list[dict[str, str]] = []
        artifacts = sorted(
            (artifact for artifact in result.artifacts),
            key=lambda artifact: str(artifact.path).replace("\\", "/"),
        )
        for artifact in artifacts:
            artifact_path = str(artifact.path).strip().replace("\\", "/")
            if not artifact_path:
                failures.append(
                    WorkloadArtifacts._failure(path_norm="", code="E_SDK_ARTIFACT_PATH_INVALID", detail="empty")
                )
                continue
            if Path(artifact_path).is_absolute():
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path, code="E_ARTIFACT_PATH_ABSOLUTE", detail=artifact_path
                    )
                )
                continue
            if ".." in Path(artifact_path).parts:
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path, code="E_ARTIFACT_PATH_TRAVERSAL", detail=artifact_path
                    )
                )
                continue
            target_path = artifact_root / artifact_path
            if target_path.is_symlink():
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path,
                        code="E_ARTIFACT_SYMLINK_FORBIDDEN",
                        detail=artifact_path,
                    )
                )
                continue
            target = target_path.resolve()
            try:
                target.relative_to(artifact_root_resolved)
            except ValueError:
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path, code="E_ARTIFACT_PATH_ESCAPE", detail=artifact_path
                    )
                )
                continue
            if not target.exists() or not target.is_file():
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path, code="E_SDK_ARTIFACT_MISSING", detail=artifact_path
                    )
                )
                continue
            file_size = target.stat().st_size
            if file_size > max_file_bytes:
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path,
                        code="E_ARTIFACT_FILE_SIZE_CAP",
                        detail=f"size={file_size} cap={max_file_bytes}",
                    )
                )
                continue
            total_bytes += file_size
            if total_bytes > max_total_bytes:
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path,
                        code="E_ARTIFACT_TOTAL_SIZE_CAP",
                        detail=f"total={total_bytes} cap={max_total_bytes}",
                    )
                )
                continue
            digest = WorkloadArtifacts._stream_sha256(target)
            if digest != artifact.digest_sha256:
                failures.append(
                    WorkloadArtifacts._failure(
                        path_norm=artifact_path,
                        code="E_SDK_ARTIFACT_DIGEST_MISMATCH",
                        detail=artifact_path,
                    )
                )
        if failures:
            raise ValueError(WorkloadArtifacts._canonical_failure_payload(failures))

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
        redacted_input = self._redacted_snapshot(input_config)
        redacted_run_result = self._redacted_snapshot(run_result)
        redacted_summary = self._redacted_snapshot(summary)
        verbose = self._provenance_verbose_enabled()
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "reliable_mode": self.reproducibility.reliable_mode_enabled(),
            "security": {
                "mode": extension.security_mode,
                "profile": extension.security_profile,
                "policy_version": extension.security_policy_version,
                "compat_fallbacks": list(extension.compat_fallbacks),
                "compat_fallback_count": len(extension.compat_fallbacks),
            },
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
            "workload": {
                "workload_id": workload.workload_id,
                "workload_version": workload.workload_version,
            },
            "input_config": input_config if verbose else {},
            "input_config_digest": input_digest,
            "input_config_redacted": redacted_input,
            "run_plan": run_plan.canonical_payload(),
            "plan_hash": plan_hash,
            "run_result": run_result if verbose else {},
            "run_result_redacted": redacted_run_result,
            "summary": summary if verbose else {},
            "summary_redacted": redacted_summary,
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
        redacted_input = self._redacted_snapshot(input_config)
        redacted_run_result = self._redacted_snapshot(run_result)
        redacted_summary = self._redacted_snapshot(summary)
        verbose = self._provenance_verbose_enabled()
        return {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "reliable_mode": self.reproducibility.reliable_mode_enabled(),
            "security": {
                "mode": extension.security_mode,
                "profile": extension.security_profile,
                "policy_version": extension.security_policy_version,
                "compat_fallbacks": list(extension.compat_fallbacks),
                "compat_fallback_count": len(extension.compat_fallbacks),
            },
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
            "input_config_redacted": redacted_input,
            "run_result": run_result if verbose else {},
            "run_result_redacted": redacted_run_result,
            "summary": summary if verbose else {},
            "summary_redacted": redacted_summary,
            "artifact_manifest": artifact_manifest,
            "artifact_root": str(artifact_root),
        }

    @staticmethod
    def build_artifact_manifest(artifact_root: Path) -> dict[str, Any]:
        artifact_root_resolved = artifact_root.resolve()
        max_file_bytes = WorkloadArtifacts._artifact_file_size_cap_bytes()
        max_total_bytes = WorkloadArtifacts._artifact_total_size_cap_bytes()
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
            file_hash = WorkloadArtifacts._stream_sha256(resolved)
            files.append({"path": rel, "sha256": file_hash})
        digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {"files": files, "manifest_sha256": digest}

    @classmethod
    def _validated_id(cls, value: str, *, code: str) -> str:
        cleaned = str(value or "").strip()
        if not cls._ID_PATTERN.fullmatch(cleaned):
            raise ValueError(f"{code}: {value}")
        return cleaned

    @staticmethod
    def _stream_sha256(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def _failure(*, path_norm: str, code: str, detail: str) -> dict[str, str]:
        normalized_path = normpath(path_norm.replace("\\", "/")) if path_norm else ""
        normalized_detail = str(detail).strip()
        detail_digest = hashlib.sha256(normalized_detail.encode("utf-8")).hexdigest()
        return {
            "path_norm": normalized_path,
            "code": code,
            "detail": normalized_detail,
            "detail_digest": detail_digest,
        }

    @staticmethod
    def _canonical_failure_payload(failures: list[dict[str, str]]) -> str:
        ordered = sorted(
            failures,
            key=lambda row: (row["path_norm"], row["code"], row["detail_digest"]),
        )
        return "E_SDK_ARTIFACT_VALIDATION_FAILED: " + json.dumps(
            {"errors": ordered},
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _artifact_file_size_cap_bytes() -> int:
        import os

        raw = str(os.getenv(WorkloadArtifacts._ARTIFACT_FILE_SIZE_CAP_BYTES_ENV, "")).strip()
        if raw:
            return max(1, int(raw))
        return WorkloadArtifacts._ARTIFACT_FILE_SIZE_CAP_BYTES_DEFAULT

    @staticmethod
    def _artifact_total_size_cap_bytes() -> int:
        import os

        raw = str(os.getenv(WorkloadArtifacts._ARTIFACT_TOTAL_SIZE_CAP_BYTES_ENV, "")).strip()
        if raw:
            return max(1, int(raw))
        return WorkloadArtifacts._ARTIFACT_TOTAL_SIZE_CAP_BYTES_DEFAULT

    @staticmethod
    def _provenance_verbose_enabled() -> bool:
        import os

        raw = str(os.getenv("ORKET_EXT_PROVENANCE_VERBOSE", "")).strip().lower()
        return raw in {"1", "true", "yes", "on"}

    @staticmethod
    def _redacted_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
        keys = sorted(str(key) for key in payload.keys())
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return {
            "keys": keys,
            "item_count": len(keys),
            "payload_digest_sha256": digest,
        }

    @staticmethod
    def _resolve_bool_setting(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return True

    @staticmethod
    def _resolve_float_setting(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
