# SDK Implementation Plan

## Phase 1: Typed Capability Providers

**What**: Replace opaque `Any` registrations with typed provider protocols.
**Why**: Extensions currently get untyped values from `capabilities.get()`. No IDE support, no runtime validation.
**Where**: `orket_extension_sdk/capabilities.py`

Tasks:
- [x] Define `TTSProvider` protocol with `synthesize()` and `list_voices()`
- [x] Define `AudioPlayer` protocol with `play()` and `stop()`
- [x] Define `AudioClip` and `VoiceInfo` data classes
- [x] Create `NullTTSProvider` and `NullAudioPlayer` (silent defaults)
- [x] Add typed accessor helpers: `capabilities.tts() -> TTSProvider`
- [x] Update preflight to validate provider types, not just presence

Files touched:
- `orket_extension_sdk/capabilities.py` (extend)
- `orket_extension_sdk/audio.py` (new - protocols + data classes + null impls)

## Phase 2: Piper TTS Backend

**What**: Implement a real `TTSProvider` backed by Piper (local, CPU, MIT licensed).
**Why**: Piper is the lightest local TTS option. Runs on CPU, dozens of pre-trained voices, fast enough for short sentences (the max_words limits in archetypes.yaml keep utterances under 16 words).
**Where**: `orket/capabilities/tts_piper.py` (Orket-level, not SDK)

Tasks:
- [ ] Install piper-tts as optional dependency
- [ ] Implement `PiperTTSProvider(TTSProvider)` with voice model path config
- [ ] Map `emotion_hint` to Piper parameters (speed, pitch variance)
- [ ] Register in `build_sdk_capability_registry()` when Piper is available
- [ ] Fall back to `NullTTSProvider` when Piper is not installed

Files touched:
- `orket/capabilities/tts_piper.py` (new)
- `orket/extensions/workload_artifacts.py` (register TTS provider)
- `pyproject.toml` (optional piper-tts dependency)

## Phase 3: TextMystery Audio Integration

**What**: Wire TextMystery's render path to request audio via SDK capability.
**Why**: Prove the capability system works end-to-end with a real extension.
**Where**: TextMystery extension

Tasks:
- [ ] Add `tts.speak` to TextMystery's `required_capabilities` in manifest
- [ ] Create `content/voices/profiles.yaml` with 4 NPC voice profiles
- [ ] Map `(archetype, decision_mode)` to `(voice_id, emotion_hint)` in render layer
- [ ] Call `ctx.capabilities.get("tts.speak").synthesize()` after text render
- [ ] Return audio alongside text in game response (dual channel)
- [ ] Graceful degradation: if `NullTTSProvider`, skip audio silently

Files touched:
- TextMystery `extension.yaml` (add capability)
- TextMystery `content/voices/profiles.yaml` (new)
- TextMystery `src/textmystery/engine/render.py` (add audio output)
- TextMystery `src/textmystery/engine/types.py` (extend RenderedResponse)

## Phase 4: Audio Playback

**What**: Platform audio output so synthesized speech actually plays.
**Why**: Phase 2-3 produce AudioClip bytes. This phase plays them.
**Where**: `orket/capabilities/audio_player.py`

Tasks:
- [ ] Implement `SounddevicePlayer(AudioPlayer)` using sounddevice library
- [ ] Register as `audio.play` capability
- [ ] TUI integration: play audio inline with text transcript display
- [ ] NullAudioPlayer for headless/CI

## Phase 5: Reforger Audio Validation

**What**: Extend reforger to validate voice profile content alongside text content.
**Why**: The reforger already validates archetypes and NPC references. Voice profiles should get the same treatment: every NPC must map to a valid voice, emotion hints must be recognized.
**Where**: `orket/reforger/routes/textmystery_persona_v0.py`

Tasks:
- [ ] Add voice profile normalization to TextMysteryPersonaRouteV0
- [ ] Add inspector checks: NPC voice profile exists, voice_id is non-empty
- [ ] Include voice profile digests in bundle_digests.json

## Dependency Flow

```
Phase 1 (SDK types)
  -> Phase 2 (Piper backend) + Phase 3 (TextMystery integration)
     -> Phase 4 (Playback)
        -> Phase 5 (Reforger validation)
```

Phases 2 and 3 can run in parallel once Phase 1 is done.

## What NOT to Build

- No streaming TTS (sentences are 8-16 words, batch is fine)
- No voice cloning (Piper's pre-trained voices are enough to start)
- No audio recording/STT (player input stays as text)
- No Vue/web frontend for audio (TUI + direct audio playback)
- No environmental audio in Phase 1-4 (R8 is deferred)
