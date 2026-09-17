# Governed-agent application command ownership

## Summary
- Owner: Orket Core.
- Date: 2026-09-16.
- Contract authority: `docs/ARCHITECTURE.md` layer and effect ownership rules.

## Delta
- `GovernedAgentCommands` owns inspection/replay repository composition,
  pause/stop control submission and operator cancellation. The CLI translates
  arguments and renders results without concrete storage or core imports.
- `submit_governed_agent` accepts frozen `GovernedAgentSubmission` and
  `GovernedAgentProviderOptions`. Caller-owned timestamp sequences and nested role
  pairs are copied into tuples. Existing provider selection remains explicit,
  with llama.cpp as the provider-neutral default and no provider fallback.
- Catalog validation and request-file decoding execute in a retained worker.
  Cancellation/timeout waits for that worker; no run is admitted after an
  interrupted preparation. Application owns provider cleanup even when loop
  composition fails, retaining cleanup through interruption.
- A CLI cancellation cannot attest teardown of another runtime's child. It
  preserves `child_confirmed_stopped=false` and retained residual uncertainty.

## Migration Plan
1. Public command arguments, response fields, exit status and retained schemas
   remain unchanged. Internal embeddings use application services instead of
   the removed private CLI composition functions; no forwarding shim is added.
2. Preserve real submit/inspect/replay/reentry, missing/malformed-input refusal,
   idempotent controls and cancellation uncertainty across native CLI processes.
3. Require source and installed Windows/Linux Python 3.11/3.12 regression proof,
   and actual installed llama.cpp continuation/API/recovery proof for this slice.
   The canonical plan records the passing candidate envelope and the separate
   structural proof for final accumulated whitespace cleanup.

## Limits and Rollback Plan
- Explicit options do not establish deep immutability for every downstream
  request, launch or decision object. Wider D2-D4 obligations remain active.
- Held-worker and client-close controls establish their named lifetime behavior;
  they do not establish arbitrary stuck-worker termination or OS containment.
- Dependency enforcement, remaining authority cycles, full-suite/hosted CI,
  capability and whole-lane acceptance remain open in the canonical plan.
- On regression, preserve failing evidence and repair the canonical application
  boundary before accepting the slice; do not restore reverse dependency shims.

## Versioning Decision
- Included in core 0.6.3, the accumulated remediation branch checkpoint.
- No wire/schema version change for these CLI commands. The broader checkpoint's
  SDK and storage migrations remain separately governed by their contracts.
