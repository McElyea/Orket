# Host Piper runtime contract

Last updated: 2026-09-13
Status: Active

## Selection and ownership

The core host implementation is `orket/capabilities/tts_piper.py`.
`ExtensionRuntimeService` and `WorkloadArtifacts` supply the application-owned
`CommandProcessSupervisor` through the core `CommandRunner` port, with their
workspace and `piper_process_cancelled` event. Direct constructors require that
port and workspace. The separately shipped SDK in-process Piper implementation
is outside this native CLI contract.

The factory selects `null` by default. Explicit unknown backends fail with
`E_TTS_BACKEND_UNSUPPORTED`; explicit Piper without a model setting fails with
`E_PIPER_MODEL_REQUIRED`. A missing command owner/workspace fails with
`E_PIPER_COMMAND_OWNER_REQUIRED`. Explicit Piper selection never silently returns
a null provider. Files and executables are discovered when the capability is used;
construction launches no process.

Existing configuration names remain `tts_backend`, `tts_model_path`,
`tts_voices_dir`, `tts_executable` and `tts_sample_rate`, with their existing
`ORKET_TTS_*` environment counterparts. New `tts_timeout_seconds` or
`ORKET_TTS_TIMEOUT_SECONDS` selects the native command deadline, default 120
seconds. It must be finite and positive. Configuration takes precedence over
the environment. Executable strings are parsed into argv, including quoted paths;
they never run through a shell. The existing `piper` to `python -m piper` selection
uses module discovery when its PATH shim is absent; there is no `--help` subprocess
probe. Discovery is not proof that a model will load or synthesize successfully.

Relative model and voice-directory paths resolve against the owning workspace.
The configured default model must exist; the catalog lists that default first.
An omitted/empty voice selects that default. Explicit IDs match case-insensitively
and the response uses the selected canonical ID. Unknown IDs fail with
`E_PIPER_VOICE_UNKNOWN`; case-insensitive collisions between different model/config
pairs fail with `E_PIPER_VOICE_AMBIGUOUS`. Neither condition silently selects another
voice. A missing default fails with `E_PIPER_DEFAULT_MODEL_UNAVAILABLE`.

The selected model's adjacent `.onnx.json` must contain an `audio.sample_rate`
positive integer. Missing/unreadable metadata fails with
`E_PIPER_MODEL_METADATA_UNAVAILABLE`; malformed metadata or rate fails with
`E_PIPER_MODEL_METADATA_INVALID`. The returned PCM rate comes from those metadata
bytes. `tts_sample_rate` / `ORKET_TTS_SAMPLE_RATE` is now an optional positive
integer expectation: omission derives the rate, invalid configuration fails with
`E_PIPER_SAMPLE_RATE_INVALID`, and disagreement fails before execution with
`E_PIPER_SAMPLE_RATE_MISMATCH`. It does not resample or relabel audio.

## Invocation and cancellation

The generic API awaits the exact builtin Piper class's `synthesize_async` directly.
Embedding subclasses retain their synchronous SDK implementation through the
owned thread drain; the host does not bypass their overrides or classify a custom
null-provider subclass as the builtin silent backend. Model/executable
filesystem discovery is offloaded and drained; the native command is then awaited
through the shared supervisor. Cancellation can therefore reach the process owner
and stop its descendants, instead of waiting for an uncancellable synthesis thread.
The synchronous SDK-compatible `synthesize` method uses the existing persistent
sync bridge to call that same async implementation. An embedding that cannot
cancel its synchronous call still has the configured native command deadline.

The host writes the validated metadata bytes to a private `.orket-piper-*`
directory under its workspace and passes that file explicitly as `--config`.
Creation and removal use the owned thread drain. The directory remains owned
through native settlement and is removed before a successful response or cancelled
call completes. Cancellation during acquisition or cleanup cannot discard that
work; cleanup failures remain errors. This binds the reported metadata digest to
the bytes supplied to the CLI even if the original sidecar changes afterward.

Windows Job and Linux subreaper ownership, bounded escalation, repeated
cancellation, capture observations and uncertainty follow
`VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`. Speech text is UTF-8 stdin; it is not
embedded in argv or cancellation telemetry. An unconfirmed native cleanup raises
`CommandExecutionUncertain` with the original result. Confirmed timeout, nonzero
exit, output limit or incomplete capture raises `PiperSynthesisError`, also with
the original result in `lifetime`. Those results cannot produce a successful clip.
Cancellation retains `CommandProcessCancelled.lifetime` and its diagnostic event.

Piper admits a 64 MiB bound per raw output stream so normal PCM can exceed the
verifier's 4 MiB default. Exceeding the bound fails the operation; partial audio is
not returned as successful synthesis. The shared runner accepts only integer
limits from 1 byte through 64 MiB. Omitting the override preserves the 4 MiB
verifier/outward default. The isolated worker validates the same bound before
command dispatch.

## API observations

`POST /v1/extensions/{extension_id}/runtime/tts/synthesize` includes
`process_lifetime`: `owned_command.v1` for a completed builtin Piper invocation,
otherwise null for providers without a native observation. The synchronous SDK
`AudioClip` shape is unchanged. Host-only `synthesize_async` returns
`PiperSynthesisResult(clip, voice, command)`; embeddings using that host method must
read its fields. The API also includes nullable `voice_metadata`: builtin Piper
reports `schema_version=piper_voice.v1`, canonical `voice_id`, model-derived
`sample_rate`, `source=model_config.audio.sample_rate`, and
`model_config_sha256` over the exact supplied config bytes. Other providers report
null. A nonempty clip requires completed exit zero,
complete capture and confirmed cleanup; zero-exit empty output still produces
`ok=false`, `tts_empty_audio`. This is distinct from the null provider's
`tts_unavailable`. Before response headers, normal shutdown cancellation returns
HTTP 503. Native failures do not become a null-backend fallback.

The generic null backend exposes no available voices: status and catalog report
`tts_available=false`, the catalog/default voice are empty, and synthesis reports
`tts_unavailable` with no audio or native receipt. Piper catalogs are discovery
observations, not backend health checks or inference receipts. A missing executable
produces no catalog; selected-model/execution errors remain explicit on synthesis.

## Limits and remaining conformance

Native ownership does not prove arbitrary provider-thread termination, external
broker effects, abrupt host-death recovery, audio playback or perceived quality.
Model weights remain operator-managed files; the metadata snapshot is not an
immutable weight snapshot or isolation against a hostile same-user filesystem.
The host validates sample-rate metadata, not the complete Piper model schema or
its semantic agreement with arbitrary weights. Live proof identifies the exact
model/configuration used. No new injected-provider close
protocol or whole-application shutdown deadline is added.
