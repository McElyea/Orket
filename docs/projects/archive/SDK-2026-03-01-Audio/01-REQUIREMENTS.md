# SDK Requirements

## R1: Workload Contract

**Status: implemented**

Extensions declare workloads via manifest. Each workload implements:
```
Workload.run(ctx: WorkloadContext, payload: dict) -> WorkloadResult
```

WorkloadContext provides: extension_id, workload_id, run_id, workspace_root, input_dir, output_dir, capabilities, seed, config.

WorkloadResult returns: ok, output, artifacts (with SHA digests), issues, metrics.

## R2: Capability System

**Status: implemented (core + typed providers)**

Workloads declare `required_capabilities` in manifest. At runtime, the capability registry is built and preflight-checked before execution. Missing capabilities fail fast with `E_SDK_CAPABILITY_MISSING`.

Current vocabulary:
- `workspace.root` - deterministic
- `artifact.root` - deterministic
- `time.now` - non-deterministic
- `rng` - deterministic (seeded)
- `model.generate` - non-deterministic
- `audio.play` - non-deterministic
- `tts.speak` - non-deterministic
- `speech.play_clip` - non-deterministic

**Gap**: Capabilities are registered as opaque `Any` values. No typed provider protocol beyond the base `CapabilityProvider`. Extensions call `ctx.capabilities.get("tts.speak")` and get back whatever was registered. This works but provides no IDE support, no validation of the returned object, and no standard interface for capability-specific operations.

## R3: Manifest Schema

**Status: implemented**

Extensions provide `extension.yaml` (or `.yml` / `.json`) with:
- manifest_version, extension_id, extension_version
- workloads: list of {workload_id, entrypoint, required_capabilities}

Parsed by ManifestParser, stored in ExtensionCatalog.

## R4: Artifact Provenance

**Status: implemented**

Every workload run produces a provenance record with: extension metadata, input config digest, run result, plan hash, timestamps.

## R5: Reproducibility

**Status: implemented**

ReproducibilityEnforcer checks git-clean state when `ORKET_RELIABLE_MODE` is set. Prevents non-deterministic runs from polluting artifact lineage.

## R6: Audio Capability - Typed Provider

**Status: implemented (SDK layer + Piper backend integration in Orket)**

### Motivation

TextMystery NPCs currently deliver all information through text dialogue. This limits the game to a keyword-matching interrogation loop with no room for subtext, atmosphere, or non-verbal clues. Audio gives NPCs a second channel: vocal tone, hesitation, pacing — information the NPC didn't choose to reveal.

The audio layer belongs to the SDK, not TextMystery. Any extension that declares `tts.speak` should get text-to-speech synthesis without importing a TTS library directly.

### Requirements

**R6.1**: Define a `TTSProvider` protocol in the SDK:
```python
class TTSProvider(Protocol):
    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        ...

    def list_voices(self) -> list[VoiceInfo]:
        ...
```

**R6.2**: `AudioClip` is a data object: `sample_rate: int`, `channels: int`, `samples: bytes`, `format: str`. Not a file path — the SDK doesn't write to disk unless the caller asks.

**R6.3**: `VoiceInfo` describes an available voice: `voice_id: str`, `display_name: str`, `language: str`, `tags: list[str]`.

**R6.4**: The SDK provides a `NullTTSProvider` that returns silence. Extensions degrade gracefully when no real TTS backend is configured.

**R6.5**: Orket registers a real `TTSProvider` implementation when a TTS backend is available (Piper, Coqui XTTS, or other local engine). The choice of backend is an Orket-level configuration, not an extension decision.
Implemented with Piper backend selection via workload/env config (`tts_backend=piper`, model path + executable). Falls back to `NullTTSProvider` if unavailable.

**R6.6**: Extensions access TTS via the capability registry:
```python
tts = ctx.capabilities.get("tts.speak")  # returns TTSProvider
clip = tts.synthesize(text="No comment.", voice_id="nick_vale", emotion_hint="defensive")
```

**R6.7**: Voice profiles are extension content, not SDK code. TextMystery defines voice profiles in its content directory (alongside archetypes.yaml) mapping NPC archetypes to voice parameters.

**R6.8**: `emotion_hint` maps to TTS parameter adjustments (pitch variance, speed, tremor). The mapping from hint to parameters lives in the TTSProvider implementation, not the extension.

### Voice Profile Schema (extension content)

TextMystery would define `content/voices/profiles.yaml`:
```yaml
version: 1
profiles:
  NICK_VALE:
    voice_id: "male_low_clipped"
    base_speed: 1.1
    emotion_map:
      neutral: {}
      defensive: {speed: 1.2, pitch_variance: 0.02}
      evasive: {speed: 0.9, pitch_variance: 0.05}
  VICTOR_SLATE:
    voice_id: "male_deep_sparse"
    base_speed: 0.85
    emotion_map:
      neutral: {pitch_variance: 0.01}
      defensive: {speed: 0.7}
      evasive: {speed: 0.6, pitch_variance: 0.08}
```

The extension reads this content and passes voice_id + emotion_hint to the SDK. The SDK doesn't parse extension-specific content schemas.

### Decision Mode to Emotion Mapping

TextMystery maps decision modes to emotion hints in its render layer:
- ANSWER -> "neutral"
- REFUSE -> "defensive"
- DONT_KNOW -> "uncertain"
- CLARIFY -> "neutral"
- UNCLASSIFIED_AMBIGUOUS -> "neutral"

This mapping is extension logic, not SDK logic.

## R7: Audio Playback Capability

**Status: implemented (SDK contracts + null provider + sounddevice backend registration)**

**R7.1**: Define an `AudioPlayer` protocol:
```python
class AudioPlayer(Protocol):
    def play(self, clip: AudioClip, blocking: bool = False) -> None:
        ...
    def stop(self) -> None:
        ...
```

**R7.2**: Register as `audio.play` in the capability registry.

**R7.3**: `NullAudioPlayer` discards clips silently (for CI, tests, headless runs).

**R7.4**: Real implementation uses platform audio (e.g., sounddevice, pyaudio). Orket-level config, not extension choice.
Implemented with optional `sounddevice` backend (`audio_backend=sounddevice`), with automatic fallback to `NullAudioPlayer` if backend deps are unavailable.

## R8: Environment Audio Capability

**Status: not started, lower priority**

Ambient/environmental audio clips tied to scenes and events. `speech.play_clip` in the vocab. Lower priority than TTS — TTS alone transforms the experience.
