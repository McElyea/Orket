from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from orket.logging import log_event
from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.audio import AudioClip, AudioPlayer, NullAudioPlayer, TTSProvider, VoiceInfo
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse, LLMProvider
from orket_extension_sdk.memory import MemoryProvider, MemoryQueryRequest, MemoryQueryResponse, MemoryWriteRequest, MemoryWriteResponse
from orket_extension_sdk.voice import (
    STTProvider,
    TranscribeRequest,
    TranscribeResponse,
    VoiceTurnControlRequest,
    VoiceTurnControlResponse,
    VoiceTurnController,
    VoiceTurnState,
)

from .sdk_capability_authorization import (
    FIRST_SLICE_CAPABILITIES,
    SdkAuthorizationEnvelope,
    SdkCapabilityAuditCase,
    capability_admitted,
    capability_declared,
    capability_family,
)

T = TypeVar("T")


@dataclass(frozen=True)
class SdkCapabilityCallRecord:
    capability_id: str
    capability_family: str
    declared: bool
    admitted: bool
    observed_result: str
    side_effect_observed: bool
    denial_class: str = ""
    error_code: str = ""
    error_message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "capability_family": self.capability_family,
            "declared": self.declared,
            "admitted": self.admitted,
            "observed_result": self.observed_result,
            "side_effect_observed": self.side_effect_observed,
            "denial_class": self.denial_class,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class SdkCapabilityTracker:
    def __init__(
        self,
        *,
        workspace_root: Path,
        envelope: SdkAuthorizationEnvelope,
        instantiated_capabilities: list[str],
        audit_case: SdkCapabilityAuditCase,
    ) -> None:
        self._workspace_root = workspace_root
        self._envelope = envelope
        self._instantiated_capabilities = list(instantiated_capabilities)
        self._audit_case = audit_case
        self._used_capabilities: set[str] = set()
        self._call_records: list[SdkCapabilityCallRecord] = []

    def invoke(
        self,
        capability_id: str,
        operation: Callable[[], T] | None,
        *,
        side_effect_observed: Callable[[T], bool],
    ) -> T:
        declared = capability_declared(self._envelope, capability_id)
        admitted = capability_admitted(self._envelope, capability_id)
        self._used_capabilities.add(capability_id)
        self._emit(
            "sdk_capability_call_start",
            capability_id=capability_id,
            declared=declared,
            admitted=admitted,
            side_effect_observed=False,
        )
        if not declared:
            self._block(capability_id, denial_class="undeclared_use")
        if not admitted:
            self._block(capability_id, denial_class="denied")
        if operation is None:
            self._block(capability_id, denial_class="admitted_unavailable")
        try:
            result = operation()
        except Exception as exc:
            self._record_exception(capability_id, exc)
            raise
        self._record_result(
            capability_id,
            result=result,
            side_effect_observed=bool(side_effect_observed(result)),
        )
        return result

    def build_report(self) -> dict[str, Any]:
        return {
            "authorization_surface": "host_authorized_capability_registry_v1",
            "authorization_basis": self._envelope.authorization_basis,
            "policy_version": self._envelope.policy_version,
            "authorization_digest": self._envelope.authorization_digest,
            "declared_capabilities": list(self._envelope.declared_capabilities),
            "admitted_capabilities": list(self._envelope.admitted_capabilities),
            "instantiated_capabilities": list(self._instantiated_capabilities),
            "used_capabilities": sorted(self._used_capabilities),
            "audit_case": self._audit_case.as_dict(),
            "call_records": [record.as_dict() for record in self._call_records],
            "blocked_calls": [
                record.as_dict() for record in self._call_records if record.observed_result == "blocked"
            ],
        }

    def _block(self, capability_id: str, *, denial_class: str) -> None:
        declared = capability_declared(self._envelope, capability_id)
        admitted = capability_admitted(self._envelope, capability_id)
        error_code = {
            "undeclared_use": "E_SDK_CAPABILITY_UNDECLARED_USE",
            "denied": "E_SDK_CAPABILITY_DENIED",
            "admitted_unavailable": "E_SDK_CAPABILITY_UNAVAILABLE",
        }[denial_class]
        error_message = f"{error_code}: {capability_id}"
        self._emit(
            "sdk_capability_call_blocked",
            capability_id=capability_id,
            declared=declared,
            admitted=admitted,
            side_effect_observed=False,
            denial_class=denial_class,
        )
        self._call_records.append(
            SdkCapabilityCallRecord(
                capability_id=capability_id,
                capability_family=capability_family(capability_id),
                declared=declared,
                admitted=admitted,
                observed_result="blocked",
                side_effect_observed=False,
                denial_class=denial_class,
                error_code=error_code,
                error_message=error_message,
            )
        )
        raise ValueError(error_message)

    def _record_exception(self, capability_id: str, exc: Exception) -> None:
        self._emit(
            "sdk_capability_call_exception",
            capability_id=capability_id,
            declared=capability_declared(self._envelope, capability_id),
            admitted=capability_admitted(self._envelope, capability_id),
            side_effect_observed=False,
            error_code=type(exc).__name__,
            error=str(exc),
        )
        self._call_records.append(
            SdkCapabilityCallRecord(
                capability_id=capability_id,
                capability_family=capability_family(capability_id),
                declared=capability_declared(self._envelope, capability_id),
                admitted=capability_admitted(self._envelope, capability_id),
                observed_result="failure",
                side_effect_observed=False,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
        )

    def _record_result(self, capability_id: str, *, result: Any, side_effect_observed: bool) -> None:
        observed_result = "success" if bool(getattr(result, "ok", True)) else "failure"
        self._emit(
            "sdk_capability_call_result",
            capability_id=capability_id,
            declared=capability_declared(self._envelope, capability_id),
            admitted=capability_admitted(self._envelope, capability_id),
            side_effect_observed=side_effect_observed,
        )
        self._call_records.append(
            SdkCapabilityCallRecord(
                capability_id=capability_id,
                capability_family=capability_family(capability_id),
                declared=capability_declared(self._envelope, capability_id),
                admitted=capability_admitted(self._envelope, capability_id),
                observed_result=observed_result,
                side_effect_observed=side_effect_observed,
            )
        )

    def _emit(
        self,
        event_name: str,
        *,
        capability_id: str,
        declared: bool,
        admitted: bool,
        side_effect_observed: bool,
        denial_class: str = "",
        error_code: str = "",
        error: str = "",
    ) -> None:
        log_event(
            event_name,
            {
                "session_id": self._envelope.run_id,
                "run_id": self._envelope.run_id,
                "extension_id": self._envelope.extension_id,
                "workload_id": self._envelope.workload_id,
                "capability_id": capability_id,
                "capability_family": capability_family(capability_id),
                "authorization_basis": self._envelope.authorization_basis,
                "declared": declared,
                "admitted": admitted,
                "side_effect_observed": side_effect_observed,
                "denial_class": denial_class,
                "error_code": error_code,
                "error": error,
            },
            workspace=self._workspace_root,
            role="extension_runtime",
        )


class GovernedLLMProvider:
    def __init__(self, *, tracker: SdkCapabilityTracker, delegate: LLMProvider | None) -> None:
        self._tracker = tracker
        self._delegate = delegate

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        operation = (lambda: self._delegate.generate(request)) if self._delegate is not None else None
        return self._tracker.invoke("model.generate", operation, side_effect_observed=lambda _result: False)

    def is_available(self) -> bool:
        return self._delegate is not None and self._delegate.is_available()


class GovernedMemoryProvider:
    def __init__(self, *, tracker: SdkCapabilityTracker, delegate: MemoryProvider | None) -> None:
        self._tracker = tracker
        self._delegate = delegate

    def write(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        operation = (lambda: self._delegate.write(request)) if self._delegate is not None else None
        return self._tracker.invoke(
            "memory.write",
            operation,
            side_effect_observed=lambda response: bool(getattr(response, "ok", False)),
        )

    def query(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        operation = (lambda: self._delegate.query(request)) if self._delegate is not None else None
        return self._tracker.invoke("memory.query", operation, side_effect_observed=lambda _response: False)


class GovernedSTTProvider:
    def __init__(self, *, tracker: SdkCapabilityTracker, delegate: STTProvider | None) -> None:
        self._tracker = tracker
        self._delegate = delegate

    def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        operation = (lambda: self._delegate.transcribe(request)) if self._delegate is not None else None
        return self._tracker.invoke("speech.transcribe", operation, side_effect_observed=lambda _response: False)


class GovernedTTSProvider:
    def __init__(self, *, tracker: SdkCapabilityTracker, delegate: TTSProvider | None) -> None:
        self._tracker = tracker
        self._delegate = delegate

    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        operation = (
            lambda: self._delegate.synthesize(
                text,
                voice_id,
                emotion_hint=emotion_hint,
                speed=speed,
            )
        ) if self._delegate is not None else None
        return self._tracker.invoke("tts.speak", operation, side_effect_observed=lambda _clip: False)

    def list_voices(self) -> list[VoiceInfo]:
        if self._delegate is None:
            return []
        return self._delegate.list_voices()


class GovernedAudioPlayer:
    def __init__(
        self,
        *,
        tracker: SdkCapabilityTracker,
        delegate: AudioPlayer | None,
        capability_id: str,
    ) -> None:
        self._tracker = tracker
        self._delegate = delegate
        self._capability_id = capability_id

    def play(self, clip: AudioClip, blocking: bool = False) -> None:
        operation = (lambda: self._invoke_play(clip=clip, blocking=blocking)) if self._delegate is not None else None
        self._tracker.invoke(
            self._capability_id,
            operation,
            side_effect_observed=self._side_effect_observed,
        )

    def stop(self) -> None:
        operation = self._invoke_stop if self._delegate is not None else None
        self._tracker.invoke(
            self._capability_id,
            operation,
            side_effect_observed=self._side_effect_observed,
        )

    def _invoke_play(self, *, clip: AudioClip, blocking: bool) -> AudioPlayer:
        if self._delegate is None:
            raise ValueError("E_SDK_CAPABILITY_UNAVAILABLE")
        self._delegate.play(clip, blocking=blocking)
        return self._delegate

    def _invoke_stop(self) -> AudioPlayer:
        if self._delegate is None:
            raise ValueError("E_SDK_CAPABILITY_UNAVAILABLE")
        self._delegate.stop()
        return self._delegate

    @staticmethod
    def _side_effect_observed(delegate: AudioPlayer) -> bool:
        return not isinstance(delegate, NullAudioPlayer)


class GovernedVoiceTurnController:
    def __init__(self, *, tracker: SdkCapabilityTracker, delegate: VoiceTurnController | None) -> None:
        self._tracker = tracker
        self._delegate = delegate

    def control(self, request: VoiceTurnControlRequest) -> VoiceTurnControlResponse:
        operation = (lambda: self._delegate.control(request)) if self._delegate is not None else None
        return self._tracker.invoke(
            "voice.turn_control",
            operation,
            side_effect_observed=lambda response: bool(getattr(response, "ok", False)),
        )

    def state(self) -> VoiceTurnState:
        operation = self._delegate.state if self._delegate is not None else None
        return self._tracker.invoke("voice.turn_control", operation, side_effect_observed=lambda _state: False)


def build_governed_sdk_capability_registry(
    *,
    raw_registry: CapabilityRegistry,
    envelope: SdkAuthorizationEnvelope,
    workspace_root: Path,
    audit_case: SdkCapabilityAuditCase,
    instantiated_capabilities: list[str],
) -> tuple[CapabilityRegistry, SdkCapabilityTracker]:
    governed_registry = CapabilityRegistry()
    raw_providers = dict(raw_registry._providers)
    for capability_id, provider in sorted(raw_providers.items()):
        if capability_id in FIRST_SLICE_CAPABILITIES:
            continue
        governed_registry.register(capability_id, provider)
    tracker = SdkCapabilityTracker(
        workspace_root=workspace_root,
        envelope=envelope,
        instantiated_capabilities=instantiated_capabilities,
        audit_case=audit_case,
    )
    memory_delegate = raw_providers.get("memory.write") or raw_providers.get("memory.query")
    llm_delegate = raw_providers.get("model.generate")
    stt_delegate = raw_providers.get("speech.transcribe")
    tts_delegate = raw_providers.get("tts.speak")
    audio_delegate = raw_providers.get("audio.play")
    speech_player_delegate = raw_providers.get("speech.play_clip")
    voice_turn_delegate = raw_providers.get("voice.turn_control")
    governed_registry.register(
        "model.generate",
        GovernedLLMProvider(tracker=tracker, delegate=llm_delegate if isinstance(llm_delegate, LLMProvider) else None),
    )
    governed_registry.register(
        "memory.write",
        GovernedMemoryProvider(
            tracker=tracker,
            delegate=memory_delegate if isinstance(memory_delegate, MemoryProvider) else None,
        ),
    )
    governed_registry.register(
        "memory.query",
        GovernedMemoryProvider(
            tracker=tracker,
            delegate=memory_delegate if isinstance(memory_delegate, MemoryProvider) else None,
        ),
    )
    governed_registry.register(
        "speech.transcribe",
        GovernedSTTProvider(tracker=tracker, delegate=stt_delegate if isinstance(stt_delegate, STTProvider) else None),
    )
    governed_registry.register(
        "tts.speak",
        GovernedTTSProvider(tracker=tracker, delegate=tts_delegate if isinstance(tts_delegate, TTSProvider) else None),
    )
    governed_registry.register(
        "audio.play",
        GovernedAudioPlayer(
            tracker=tracker,
            delegate=audio_delegate if isinstance(audio_delegate, AudioPlayer) else None,
            capability_id="audio.play",
        ),
    )
    governed_registry.register(
        "speech.play_clip",
        GovernedAudioPlayer(
            tracker=tracker,
            delegate=speech_player_delegate if isinstance(speech_player_delegate, AudioPlayer) else None,
            capability_id="speech.play_clip",
        ),
    )
    governed_registry.register(
        "voice.turn_control",
        GovernedVoiceTurnController(
            tracker=tracker,
            delegate=voice_turn_delegate if isinstance(voice_turn_delegate, VoiceTurnController) else None,
        ),
    )
    return governed_registry, tracker
