# Implementation Plan: Voice/STT and Turn Control

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 1 (SDK/host seam hardening)
**Depends on**: 03-CAPABILITY-WIRING (protocols + models)
**Estimated Scope**: ~12 files touched, ~700 lines added

## Problem

Companion MVP requires STT voice input and manual silence-delay turn-finalization control. No STT subsystem exists. No voice turn lifecycle state machine exists. No silence-delay parameter exists anywhere. The TTS side exists (PiperTTSProvider) but is output-only and excluded from MVP.

## Current State

**Exists**:
- `TTSProvider` protocol + `PiperTTSProvider` (output, not needed for MVP)
- `AudioPlayer` protocol + `NullAudioPlayer` (output)
- `audio.play`, `tts.speak`, `speech.play_clip` capabilities registered

**Does NOT exist**:
- STT provider protocol or implementation
- `speech.transcribe` capability
- `voice.turn_control` capability
- Turn lifecycle state machine (listening -> transcribing -> waiting_for_silence -> finalizing -> completed)
- Silence-delay parameter or bounds validation
- Voice degradation to text-only mode

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No STT provider protocol | BLOCKING | No way to ingest voice input |
| No turn lifecycle FSM | BLOCKING | No state management for voice turns |
| No silence-delay control | BLOCKING | MVP acceptance gate |
| No turn-finalization logic | BLOCKING | No way to determine when voice input is "done" |
| No text-only degradation | HIGH | MVP must work without STT |
| No STT provider implementation | HIGH | Need at least one working STT backend |
| No partial transcript support | LOW | Optional for MVP |
| Silence-delay bounds not defined | MEDIUM | Need min/max host-validated bounds |

## Key Authority Rule

Silence-delay expiration and turn-finalization are **host-controlled lifecycle decisions**. STT providers supply transcription input and availability/segment signals only; they must not become the authority for turn-finalization timing.

## Implementation Steps

### Step 1: Voice turn lifecycle FSM

```python
# orket_extension_sdk/voice.py

class VoiceTurnState(str, Enum):
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    WAITING_FOR_SILENCE = "waiting_for_silence"
    FINALIZING = "finalizing"
    COMPLETED = "completed"  # terminal

VALID_TRANSITIONS = {
    VoiceTurnState.LISTENING: {VoiceTurnState.TRANSCRIBING, VoiceTurnState.COMPLETED},
    VoiceTurnState.TRANSCRIBING: {VoiceTurnState.WAITING_FOR_SILENCE, VoiceTurnState.COMPLETED},
    VoiceTurnState.WAITING_FOR_SILENCE: {VoiceTurnState.FINALIZING, VoiceTurnState.LISTENING, VoiceTurnState.COMPLETED},
    VoiceTurnState.FINALIZING: {VoiceTurnState.COMPLETED},
    VoiceTurnState.COMPLETED: set(),  # terminal
}
```

Key rules from the plan:
- Explicit user stop/submit always overrides silence-delay waiting (force -> COMPLETED), short-circuiting any pending silence timer and producing a stable terminal boundary immediately
- Manual silence-delay is voice-only; never affects text submission
- Text submission is always explicit and unaffected by voice settings

**State observability**: With MVP chunked-upload transport, `LISTENING` is primarily UI-local during recording. It becomes host-observed when audio is uploaded (transitions to `TRANSCRIBING`). Document which states are UI-observable vs host-internal.

### Step 2: Silence-delay parameter with bounds validation

```python
SILENCE_DELAY_MIN_SEC = 0.5
SILENCE_DELAY_MAX_SEC = 10.0
SILENCE_DELAY_DEFAULT_SEC = 2.0

class SilenceDelayConfig(BaseModel):
    delay_sec: float = SILENCE_DELAY_DEFAULT_SEC

    @model_validator(mode="after")
    def clamp_to_bounds(self) -> Self:
        self.delay_sec = max(SILENCE_DELAY_MIN_SEC, min(SILENCE_DELAY_MAX_SEC, self.delay_sec))
        return self
```

- Profile-persisted (via profile_memory key `companion_setting.silence_delay_sec`)
- Session-overridable (in-memory override, resets on new session)
- Host-validated: UI sends desired value, host clamps to bounds

### Step 3: VoiceTurnController (host-side)

```python
class HostVoiceTurnController:
    def __init__(self, stt_provider: STTProvider | None, silence_config: SilenceDelayConfig):
        self._state = VoiceTurnState.LISTENING
        self._stt = stt_provider
        self._silence_config = silence_config
        self._transcript_buffer: list[str] = []
        self._silence_timer: asyncio.Task | None = None

    async def get_state(self) -> TurnControlState: ...

    async def send_command(self, command: TurnControlCommand) -> TurnControlState:
        match command.action:
            case "start_listening":
                self._transition(VoiceTurnState.LISTENING)
            case "stop_listening":
                self._transition(VoiceTurnState.FINALIZING)
            case "submit":
                self._cancel_silence_timer()  # short-circuit immediately
                self._transition(VoiceTurnState.COMPLETED)
            case "cancel":
                self._cancel_silence_timer()
                self._transcript_buffer.clear()
                self._transition(VoiceTurnState.COMPLETED)
            case "set_silence_delay":
                self._silence_config.delay_sec = clamp(command.silence_delay_sec)
        return await self.get_state()

    async def _on_silence_timer_expired(self):
        """
        Host-owned decision: silence delay has expired.
        STT providers do NOT call this -- the host silence timer does.
        """
        if self._state == VoiceTurnState.WAITING_FOR_SILENCE:
            self._transition(VoiceTurnState.FINALIZING)
            self._transition(VoiceTurnState.COMPLETED)
```

### Step 4: STT provider protocol and null implementation

Protocol defined in Plan 03. Add null/stub:

```python
class NullSTTProvider:
    """Used when STT is unavailable. Companion degrades to text-only."""
    async def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        raise CapabilityUnavailableError("stt_unavailable", "STT provider not configured")

    @property
    def available(self) -> bool:
        return False
```

### Step 5: STT provider implementation

Candidate: `faster-whisper` (local, no cloud dependency, MIT license, fits local-first sovereignty).

The provider contract accepts structured audio input (`TranscribeRequest`). The host implementation handles engine-specific decoding/file buffering internally. Provider examples should not overcommit to a raw API shape.

```python
class WhisperSTTProvider:
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        self._model_size = model_size
        self._device = device
        self._model = None  # lazy init

    async def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        model = self._ensure_model()
        # Handle audio input conversion internally
        audio_source = self._prepare_audio(request)
        segments, info = await asyncio.to_thread(model.transcribe, audio_source, language=request.language)
        text = " ".join(seg.text for seg in segments)
        return TranscribeResponse(text=text, confidence=info.language_probability, language=info.language)

    @property
    def available(self) -> bool:
        return True
```

### Step 6: Text-only degradation

If `stt_provider.available` is False:
- UI shows visible "Voice unavailable -- text only" state
- Voice controls are disabled/hidden in UI
- `speech.transcribe` capability returns structured error with code `stt_unavailable`
- All text submission paths remain fully functional
- No hidden failure mode (plan requirement)

### Step 7: Host API endpoints for voice

```
POST /api/v1/companion/voice/start    -> start listening (returns TurnControlState)
POST /api/v1/companion/voice/stop     -> stop listening, finalize
POST /api/v1/companion/voice/submit   -> explicit submit (overrides silence wait)
POST /api/v1/companion/voice/cancel   -> cancel current voice input
GET  /api/v1/companion/voice/state    -> current TurnControlState
POST /api/v1/companion/voice/transcribe -> upload audio for transcription
PUT  /api/v1/companion/voice/config   -> update silence_delay_sec (profile-persisted)
GET  /api/v1/companion/voice/config   -> current voice config including STT availability
```

### Step 8: Transport decision

MVP transport is **chunked upload** (explicitly chosen). Streaming is deferred to post-MVP.

- UI records audio, sends as POST with audio blob
- Host transcribes, returns transcript
- Voice lifecycle/state modeling reflects this chunked-upload transport, not an implied streaming-native runtime

Turn-complete boundary: response includes both terminal event (`state: "completed"`) and final result (`transcript: "..."` in `TurnControlState`).

## Acceptance Criteria

1. Voice turn lifecycle FSM enforces valid state transitions
2. Explicit user stop/submit always overrides silence-delay waiting, short-circuiting any pending timer immediately
3. Manual silence-delay is adjustable from UI, clamped to host-validated bounds
4. Silence-delay value persists in profile, overridable per session
5. Text submission is completely independent of voice settings
6. STT unavailable degrades to text-only with visible UI state, no hidden failure
7. At least one working STT implementation (Whisper or equivalent)
8. Host API exposes turn state transitions and turn-complete boundary
9. Turn-complete response includes final transcript content
10. Host-owned silence-delay behavior is enforceable and testable independently of the selected STT engine implementation

## Files to Create/Modify

| Action | Path |
|--------|------|
| CREATE | `orket_extension_sdk/voice.py` (FSM, states, protocols, models) |
| CREATE | `orket/capabilities/host_voice_controller.py` |
| CREATE | `orket/capabilities/host_stt_provider.py` (Whisper impl) |
| CREATE | `orket/capabilities/null_stt_provider.py` |
| MODIFY | `orket_extension_sdk/capabilities.py` (register speech.transcribe, voice.turn_control) |
| CREATE | `orket/interfaces/routers/voice_router.py` (API endpoints) |
| MODIFY | `orket/interfaces/api.py` (mount voice router) |
| CREATE | `tests/core/test_voice_turn_fsm.py` |
| CREATE | `tests/application/test_voice_turn_controller.py` |
| CREATE | `tests/application/test_stt_degradation.py` |
| CREATE | `tests/application/test_silence_delay_independent_of_stt.py` |
| CREATE | `tests/interfaces/test_voice_api.py` |
