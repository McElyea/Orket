# Host Piper native ownership and availability

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/PIPER_RUNTIME_CONTRACT.md` and native/API lifecycle specs.
- Trigger: the thread-drain checkpoint still waited for an unsupervised Piper
  process, and null TTS status disagreed with synthesis availability.

## Delta
- The host adapter requires an application `CommandRunner` and workspace. API and
  SDK workload composition supply the existing native supervisor; no second
  process owner or direct-child fallback is introduced.
- API Piper synthesis directly awaits native execution; synchronous SDK use bridges
  to that implementation. A finite configurable deadline defaults to 120 seconds.
- The directly awaited path is limited to the exact builtin class. Injected
  subclasses preserve their synchronous overrides and declared voice catalogs;
  builtin-null classification does not override custom provider behavior.
- Shared capture admits an optional validated bound through 64 MiB. Piper uses
  64 MiB for PCM; existing verifier/outward defaults remain 4 MiB.
- Construction no longer launches executable probes or silently changes an explicit
  failed/unsupported selection into null TTS. The generic null catalog/status now
  reports unavailable consistently. Configured empty output is `tts_empty_audio`.
- The generic TTS API adds nullable `process_lifetime`; the SDK AudioClip shape
  remains unchanged. Cancellation emits `piper_process_cancelled` with native
  lifetime fields. Unconfirmed cleanup and failed capture cannot yield valid audio.

## Migration Plan
1. Direct core host Piper embeddings must supply their application command owner
   and workspace. SDK protocol consumers keep their synchronous method.
2. Correct explicit model/executable/backend configuration when rejected. Use
   explicit/default `null` only when no speech backend is intended.
3. Set `tts_timeout_seconds` or `ORKET_TTS_TIMEOUT_SECONDS` where a different finite
   native deadline is needed. Handle cancellation, failure and empty audio distinctly.
4. Keep native observations and failed proof attempts in the canonical plan. Do not
   reinterpret discovery as successful inference or certify unverified voice assets.

## Rollback Plan
1. Stop affected speech admission if native ownership cannot be established.
2. Retain failed/uncertain results and prior artifact identities. Do not restore
   unsupervised processes or silently relabel explicit Piper selection as null.

## Versioning Decision
- Core candidate behavior/contract repair with existing SDK 0.7.0a1. No release,
  tag, publication or SDK schema change.
- Voice fallback identity, sample-rate provenance, other providers and broader
  workload/host-death recovery remain active conformance obligations.
