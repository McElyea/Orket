# Host Piper voice identity and sample-rate truth

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/PIPER_RUNTIME_CONTRACT.md`.
- Trigger: unknown IDs could echo one voice while synthesizing another, and a
  configured rate could relabel PCM without matching model metadata.

## Delta
- Empty voice requests select the configured default, which leads the catalog.
  Explicit IDs resolve case-insensitively to a canonical ID; unknown IDs and
  conflicting model/config pairs fail before native admission.
- Relative assets use the owning workspace. Missing configured defaults fail;
  discovery does not substitute a different model.
- Validated adjacent model metadata supplies the sample rate. Optional configured
  rates assert agreement. A private owned config snapshot supplies those exact
  bytes to Piper; cancellation drains acquisition and cleanup.
- The API adds nullable `voice_metadata` with canonical ID, rate, provenance and
  config SHA-256. The synchronous SDK `AudioClip` contract remains unchanged.
  Host-only async consumers now receive `PiperSynthesisResult` fields.

## Migration Plan
1. Use a catalog voice ID or omit the ID for the configured default. Repair
   ambiguous assets and missing/default metadata when rejected.
2. Remove redundant sample-rate overrides or set them to the model's actual rate.
   Supply relative paths from the owning workspace and permit private config
   creation/removal there.
3. Update direct host async callers to read `clip`, `voice` and `command` fields.
   Retain failed/uncertain native receipts and source metadata evidence.

## Rollback Plan
1. Stop affected speech admission if asset identity or rate cannot be established.
2. Preserve failed observations; do not restore silent voice substitution or
   rate relabeling to recover successful responses.

## Versioning Decision
- Core candidate contract repair; SDK 0.7.0a1 is unchanged. No release or tag.
- This does not certify arbitrary model weights, full model schemas, hostile
  filesystem isolation, perceived quality or all BT-4 obligations.
