from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.capabilities.audio_player import build_audio_player
from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket.capabilities.tts_piper import build_tts_provider
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.services.scoped_memory_store import MemoryControls
from orket_extension_sdk.audio import NullAudioPlayer
from orket_extension_sdk.capabilities import CapabilityRegistry

from .artifact_provenance import ArtifactProvenanceBuilder
from .contracts import Workload
from .reproducibility import ReproducibilityEnforcer


class WorkloadArtifacts:
    """Capability registration plus delegated artifact/provenance helpers for extension runs."""

    def __init__(self, project_root: Path, reproducibility: ReproducibilityEnforcer) -> None:
        self.reproducibility = reproducibility
        self._artifacts = ArtifactProvenanceBuilder(project_root, reproducibility)

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
                if capability_id and not registry.has(capability_id):
                    registry.register(capability_id, provider)
        if not registry.has("tts.speak"):
            registry.register("tts.speak", build_tts_provider(input_config=input_config))
        if not registry.has("audio.play"):
            registry.register("audio.play", build_audio_player(input_config=input_config))
        if not registry.has("model.generate"):
            requested_model = str(input_config.get("model") or input_config.get("model_id") or "").strip()
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
                    model=requested_model or DEFAULT_LOCAL_MODEL,
                    temperature=temperature,
                    seed=seed,
                ),
            )
        if not registry.has("memory.write") or not registry.has("memory.query"):
            memory_settings = input_config.get("memory") if isinstance(input_config.get("memory"), dict) else {}
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
            voice_settings = input_config.get("voice") if isinstance(input_config.get("voice"), dict) else {}
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

    def validate_sdk_artifacts(self, result: Any, artifact_root: Path) -> None:
        self._artifacts.validate_sdk_artifacts(result, artifact_root)

    def artifact_root(self, extension_id: str, workload_id: str, plan_hash: str, input_config: dict[str, Any]) -> Path:
        return self._artifacts.artifact_root(extension_id, workload_id, plan_hash, input_config)

    @staticmethod
    def run_validators(workload: Workload, run_result: dict[str, Any], artifact_root: Path) -> list[str]:
        return ArtifactProvenanceBuilder.run_validators(workload, run_result, artifact_root)

    def build_provenance(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._artifacts.build_provenance(*args, **kwargs)

    def build_sdk_provenance(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._artifacts.build_sdk_provenance(*args, **kwargs)

    def build_artifact_manifest(self, artifact_root: Path, **kwargs: Any) -> dict[str, Any]:
        return self._artifacts.build_artifact_manifest(artifact_root, **kwargs)

    def artifact_file_size_cap_bytes(self) -> int:
        return self._artifacts._artifact_file_size_cap_bytes()

    def artifact_total_size_cap_bytes(self) -> int:
        return self._artifacts._artifact_total_size_cap_bytes()

    def reliable_require_clean_git_enabled(self) -> bool:
        return self._artifacts._reliable_require_clean_git_enabled()

    def provenance_verbose_enabled(self) -> bool:
        return self._artifacts._provenance_verbose_enabled()

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
