# SDK Ollama full-input contract delta

## Summary
- Owner: Orket Core; date: 2026-10-10; core version: 0.8.3, SDK unchanged.
- Issue: #6. Generic extension generation could trim/drop a user message and
  call Ollama without an explicit context, then return `ok: true`.
- Authorities: `MODEL_GENERATION_OPTIONS.md`,
  `PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md`,
  `PROVIDER_INFERENCE_CLIENT_OWNERSHIP.md`.

## Delta and migration
Builtin SDK Ollama generation now selects the existing guarded native transport
and asks the existing prompt policy for full-input admission. The resolved host
profile supplies input capacity; output reservation and admission use the shared
budget contract. Default and per-request API providers follow the same path.
Missing profiles, excessive input/output, unavailable guards and invalid model
capacity refuse before inference. HTTP budget errors use the existing 400
`detail: {ok: false, code, message}` envelope.

Operators require Ollama >=0.24.0 and an admitted host profile, even in shadow
mode. Scope oversized requests or explicitly select a larger host context via
`ORKET_LOCAL_PROMPT_PROFILE_REGISTRY_PATH`. Output requests above the profile
ceiling now refuse instead of being silently capped. The conservative byte
estimate is not an exact tokenizer measurement.

Other providers, streaming, third-party injected SDK providers, wire schemas and
governed completion authority are unchanged. This closes the reported generic
Ollama path; it does not establish non-truncation for every model integration.

## Verification and rollback
Real TCP API/SDK/policy integration observes complete provider messages and
guards, no generation on admission refusal, structured errors and owned cleanup.
Fresh installed live Ollama reproduction and post-fix evidence belong in
`docs/releases/0.8.3/PROOF_REPORT.md`.

Rollback requires reverting the change together with its source-of-truth docs;
do not disable the guards or describe the former path as safe. No stored-state
migration is introduced. Existing run records remain historical evidence.
