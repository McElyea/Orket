# Implementation Plan: Capability Wiring

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 1 (SDK/host seam hardening)
**Depends on**: 02-SDK-PACKAGE-HARDENING
**Estimated Scope**: ~10 files touched, ~600 lines added

## Problem

The capability registry defines vocabulary for 9 capabilities but only implements `audio.play`, `tts.speak`, and `speech.play_clip`. Companion requires `model.generate`, `memory.write`, `memory.query`, `speech.transcribe`, and `voice.turn_control` -- none of which have implementations or typed request/response models.

## Current State

**Defined in `_CAPABILITY_VOCAB` (capabilities.py)**:
- `workspace.root` (deterministic) -- implemented
- `artifact.root` (deterministic) -- implemented
- `time.now` (non-deterministic) -- implemented
- `rng` (deterministic) -- implemented
- `model.generate` (non-deterministic) -- NOT implemented (LLMProvider protocol exists but no registry wiring)
- `audio.play` (non-deterministic) -- implemented (NullAudioPlayer fallback)
- `tts.speak` (non-deterministic) -- implemented (PiperTTSProvider)
- `speech.play_clip` (non-deterministic) -- implemented (AudioPlayer)
- `screen.render` (deterministic) -- NOT implemented

**SDK protocol stubs that exist but aren't wired**:
- `LLMProvider` in `llm.py`: `generate(request: GenerateRequest) -> GenerateResponse`
- `TTSProvider` in `audio.py`: `synthesize(text, voice_id, emotion_hint, speed) -> AudioClip`

**Not defined at all**:
- `memory.write` -- no capability, no protocol, no models
- `memory.query` -- no capability, no protocol, no models
- `speech.transcribe` -- no capability, no protocol, no models
- `voice.turn_control` -- no capability, no protocol, no models

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| `model.generate` not wired | BLOCKING | Companion cannot call LLM without this |
| `memory.write` missing entirely | BLOCKING | Companion memory writes have no seam |
| `memory.query` missing entirely | BLOCKING | Companion memory reads have no seam |
| `speech.transcribe` missing entirely | BLOCKING | Voice input has no seam |
| `voice.turn_control` missing entirely | HIGH | Turn lifecycle management has no seam |
| No typed models for new capabilities | HIGH | No Pydantic request/response schemas |
| No error codes for capability failures | MEDIUM | Failures would be unstructured exceptions |

## Implementation Steps

### Step 1: Define typed models for each new capability

Public capability contracts live in dedicated SDK modules by concern (`llm.py`, `memory.py`, `voice.py`), not accumulated in `capabilities.py`. `capabilities.py` remains vocabulary/registry-oriented only. All public models use Pydantic `BaseModel`.

```python
# orket_extension_sdk/llm.py (extend existing)
class GenerateRequest(BaseModel):
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int | None = None
    stop: list[str] | None = None

class GenerateResponse(BaseModel):
    content: str
    model: str
    usage: dict[str, int] | None = None
    finish_reason: str = "stop"

# orket_extension_sdk/memory.py (new)
class MemoryWriteRequest(BaseModel):
    scope: Literal["session", "profile"]
    key: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scope_fields(self) -> Self:
        if self.scope == "profile" and not self.key:
            raise ValueError("key is required for profile scope")
        if self.scope == "session" and self.key is not None:
            raise ValueError("key must be omitted for session scope")
        return self

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_json_safe(cls, v: dict) -> dict:
        import json
        json.dumps(v)  # raises on non-serializable content
        return v

class MemoryWriteResponse(BaseModel):
    ok: bool
    record_id: str

class MemoryQueryRequest(BaseModel):
    scope: Literal["session", "profile"]
    query: str | None = None
    key: str | None = None    # exact key lookup (profile only)
    limit: int = 10

class MemoryQueryResponse(BaseModel):
    records: list[MemoryRecord]

class MemoryRecord(BaseModel):
    record_id: str
    scope: str
    key: str | None
    content: str
    metadata: dict[str, Any]
    created_at: str  # ISO 8601

# orket_extension_sdk/voice.py (new)
class TranscribeRequest(BaseModel):
    audio_data: bytes | None = None
    audio_path: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def validate_single_input(self) -> Self:
        if self.audio_data is None and self.audio_path is None:
            raise ValueError("exactly one of audio_data or audio_path is required")
        if self.audio_data is not None and self.audio_path is not None:
            raise ValueError("exactly one of audio_data or audio_path is required")
        return self

class TranscribeResponse(BaseModel):
    text: str
    is_partial: bool = False
    confidence: float | None = None
    language: str | None = None

class TurnControlState(BaseModel):
    state: Literal["listening", "transcribing", "waiting_for_silence", "finalizing", "completed"]
    silence_delay_sec: float | None = None
    transcript_so_far: str = ""

class TurnControlCommand(BaseModel):
    action: Literal["start_listening", "stop_listening", "submit", "cancel", "set_silence_delay"]
    silence_delay_sec: float | None = None
```

### Step 2: Add capabilities to vocabulary

Update `_CAPABILITY_VOCAB` in `capabilities.py`:
```python
"memory.write": {"deterministic": False},
"memory.query": {"deterministic": False},  # not overclaimed; retrieval order depends on content
"speech.transcribe": {"deterministic": False},
"voice.turn_control": {"deterministic": False},
```

Note: `memory.query` is marked non-deterministic. Determinism should only be claimed when retrieval order, filtering, and tie-break rules are fully specified and host-controlled. Do not overclaim at the vocabulary layer.

### Step 3: Define provider protocols

`voice.turn_control` is modeled as a stateful host-controlled lifecycle seam. Turn lifecycle/state semantics are owned by the host/runtime contract, not treated as a simple stateless function call. The capability exists for discoverability and invocation.

```python
# orket_extension_sdk/memory.py
class MemoryProvider(Protocol):
    async def write(self, request: MemoryWriteRequest) -> MemoryWriteResponse: ...
    async def query(self, request: MemoryQueryRequest) -> MemoryQueryResponse: ...

# orket_extension_sdk/voice.py
class STTProvider(Protocol):
    async def transcribe(self, request: TranscribeRequest) -> TranscribeResponse: ...

class VoiceTurnController(Protocol):
    """
    Stateful host-controlled lifecycle seam.
    State transitions and turn-finalization are host-owned decisions.
    """
    async def get_state(self) -> TurnControlState: ...
    async def send_command(self, command: TurnControlCommand) -> TurnControlState: ...
```

### Step 4: Wire model.generate to LocalModelProvider

In host-side code (`orket/capabilities/` module):
- Create `HostLLMProvider` that wraps `LocalModelProvider.complete()` into `GenerateRequest/Response`
- Register as `model.generate` in `build_sdk_capability_registry()`
- Reuse existing `llm.py` models where possible instead of duplicating shapes

### Step 5: Wire memory capabilities to MemoryStore

- Create `HostMemoryProvider` implementing `MemoryProvider` protocol
- Wraps `MemoryStore.remember()` and `MemoryStore.search()` with scope routing
- Requires session_memory vs profile_memory split (see Plan 04)

### Step 6: Define error codes for capability failures

Capability failure surfaces must align to a single normalized host/runtime error convention. Do not introduce a parallel ad hoc error taxonomy if the repo already has a stable error-surface pattern (see `orket/exceptions.py` hierarchy).

```python
# Extend existing OrketError hierarchy if appropriate, or define capability-specific codes
# that map cleanly to existing patterns:
E_CAPABILITY_UNAVAILABLE = "capability_unavailable"
E_PROVIDER_TIMEOUT = "provider_timeout"
E_INVALID_REQUEST = "invalid_request"
E_MEMORY_WRITE_DENIED = "memory_write_denied"
E_STT_UNAVAILABLE = "stt_unavailable"
E_TURN_CONTROL_INVALID_STATE = "turn_control_invalid_state"
```

## Acceptance Criteria

1. All 5 new capabilities appear in `_CAPABILITY_VOCAB`
2. Each capability has typed Pydantic request/response models with field validation
3. `model.generate` wired to actual LLM provider and produces real completions
4. `memory.write` and `memory.query` wired to memory store (after Plan 04)
5. `speech.transcribe` and `voice.turn_control` have protocol + null/stub implementations
6. `validate_capabilities()` correctly validates required capabilities lists including new entries
7. Error codes align with existing repo error conventions
8. Public capability models validate independently of host runtime import paths and are consumable from the external Companion repo without any `orket.*` import dependency

## Files to Create/Modify

| Action | Path |
|--------|------|
| MODIFY | `orket_extension_sdk/capabilities.py` (vocab only, no models) |
| CREATE | `orket_extension_sdk/memory.py` (MemoryProvider protocol + models) |
| CREATE | `orket_extension_sdk/voice.py` (STTProvider, VoiceTurnController + models) |
| MODIFY | `orket_extension_sdk/llm.py` (Pydantic models, ensure alignment) |
| CREATE | `orket/capabilities/host_llm_provider.py` |
| CREATE | `orket/capabilities/host_memory_provider.py` |
| CREATE | `orket/capabilities/host_stt_provider.py` (stub) |
| CREATE | `orket/capabilities/host_voice_controller.py` (stub) |
| MODIFY | `orket/extensions/workload_artifacts.py` (register new capabilities) |
| CREATE | `tests/sdk/test_capability_models.py` |
| CREATE | `tests/sdk/test_capability_wiring.py` |
