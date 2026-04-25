from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.capabilities.audio_player import build_audio_player
from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.capabilities.sdk_static_provider import StaticLLMCapabilityProvider
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket.capabilities.tts_piper import build_tts_provider
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.services.scoped_memory_store import MemoryControls
from orket_extension_sdk.audio import NullAudioPlayer
from orket_extension_sdk.capabilities import CapabilityRegistry

from .artifact_provenance import ArtifactProvenanceBuilder
from .contracts import Workload
from .reproducibility import ReproducibilityEnforcer
from .sdk_capability_authorization import FIRST_SLICE_CAPABILITIES


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
        extension_id: str = "",
        admitted_capabilities: set[str] | None = None,
        extra_first_slice_capabilities: set[str] | None = None,
    ) -> CapabilityRegistry:
        registry = CapabilityRegistry()
        registry.register("workspace.root", str(workspace))
        registry.register("artifact.root", str(artifact_root))
        narrowed_first_slice = set(admitted_capabilities or ())
        child_extra_first_slice = set(extra_first_slice_capabilities or ())
        enabled_first_slice = narrowed_first_slice | child_extra_first_slice
        configured = input_config.get("capabilities")
        if isinstance(configured, dict):
            items = sorted((str(key).strip(), value) for key, value in configured.items())
            for capability_id, provider in items:
                if not WorkloadArtifacts._capability_enabled(
                    capability_id=capability_id,
                    admitted_capabilities=admitted_capabilities,
                    enabled_first_slice=enabled_first_slice,
                ):
                    continue
                if capability_id and not registry.has(capability_id):
                    registry.register(capability_id, WorkloadArtifacts._materialize_configured_provider(capability_id, provider))
        if (
            WorkloadArtifacts._capability_enabled(
                capability_id="tts.speak",
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has("tts.speak")
        ):
            registry.register("tts.speak", build_tts_provider(input_config=input_config))
        if (
            WorkloadArtifacts._capability_enabled(
                capability_id="audio.play",
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has("audio.play")
        ):
            registry.register("audio.play", build_audio_player(input_config=input_config))
        if (
            WorkloadArtifacts._capability_enabled(
                capability_id="model.generate",
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has("model.generate")
        ):
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
        if any(
            WorkloadArtifacts._capability_enabled(
                capability_id=capability_id,
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has(capability_id)
            for capability_id in ("memory.write", "memory.query")
        ):
            raw_memory_settings = input_config.get("memory")
            memory_settings: dict[str, Any] = (
                {str(key): value for key, value in raw_memory_settings.items()}
                if isinstance(raw_memory_settings, dict)
                else {}
            )
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
                extension_id=extension_id,
            )
            if (
                WorkloadArtifacts._capability_enabled(
                    capability_id="memory.write",
                    admitted_capabilities=admitted_capabilities,
                    enabled_first_slice=enabled_first_slice,
                )
                and not registry.has("memory.write")
            ):
                registry.register("memory.write", memory_provider)
            if (
                WorkloadArtifacts._capability_enabled(
                    capability_id="memory.query",
                    admitted_capabilities=admitted_capabilities,
                    enabled_first_slice=enabled_first_slice,
                )
                and not registry.has("memory.query")
            ):
                registry.register("memory.query", memory_provider)
        if (
            WorkloadArtifacts._capability_enabled(
                capability_id="speech.transcribe",
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has("speech.transcribe")
        ):
            registry.register("speech.transcribe", HostSTTCapabilityProvider())
        if (
            WorkloadArtifacts._capability_enabled(
                capability_id="voice.turn_control",
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has("voice.turn_control")
        ):
            raw_voice_settings = input_config.get("voice")
            voice_settings: dict[str, Any] = (
                {str(key): value for key, value in raw_voice_settings.items()}
                if isinstance(raw_voice_settings, dict)
                else {}
            )
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
        if (
            WorkloadArtifacts._capability_enabled(
                capability_id="speech.play_clip",
                admitted_capabilities=admitted_capabilities,
                enabled_first_slice=enabled_first_slice,
            )
            and not registry.has("speech.play_clip")
        ):
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

    @staticmethod
    def _redacted_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
        return ArtifactProvenanceBuilder._redacted_snapshot(payload)

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

    @staticmethod
    def _capability_enabled(
        *,
        capability_id: str,
        admitted_capabilities: set[str] | None,
        enabled_first_slice: set[str],
    ) -> bool:
        if admitted_capabilities is None:
            return True
        return capability_id not in FIRST_SLICE_CAPABILITIES or capability_id in enabled_first_slice

    @staticmethod
    def _materialize_configured_provider(capability_id: str, provider: Any) -> Any:
        if capability_id == "model.generate" and isinstance(provider, dict):
            provider_kind = str(provider.get("provider") or provider.get("kind") or "").strip().lower()
            if provider_kind == "static_llm":
                return StaticLLMCapabilityProvider(
                    text=str(provider.get("text") or ""),
                    model=str(provider.get("model") or "static-test-model"),
                )
        return provider
