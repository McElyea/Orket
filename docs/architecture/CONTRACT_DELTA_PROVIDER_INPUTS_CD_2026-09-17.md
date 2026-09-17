# Captured provider preparation inputs and observations

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Status: source and separate installed live envelopes pass; the current four-cell installed gate passes. Full changed-file Ruff and whole-plan acceptance remain open.
- Affected contracts: provider identity, target values, environment capture,
  inventory/load worker lifetime and load observation claims.

## Delta
- Pure provider identity/defaults and `ProviderRuntimeTarget` values live in
  `orket/core/contracts/provider_runtime.py`. Runtime target preparation remains
  application-owned in `orket/runtime/config/provider_runtime_target.py`.
- Target model-name sequences are captured tuples. Nested GGUF records use the
  existing SDK `FrozenJson` value and core canonical JSON validation; unsupported
  values refuse rather than invoking arbitrary string conversion. `to_payload()`
  returns independent ordinary records with the existing serialized fields.
- Async target resolution and model listing capture a supplied environment mapping
  before awaiting; omission captures the process environment at entry. Base URL,
  quarantine and GGUF settings use that captured mapping during preparation.
- `LocalModelProvider` accepts an explicit environment mapping and captures it at
  construction; omission captures the process environment then. Its provider,
  temperature/seed, endpoint/key, response-format and preparation settings use the
  captured values. Later environment edits require a new client to take effect.
- Admitted synchronous inventory/load workers remain owned through repeated
  cancellation and elapsed caller timeout. A worker failure takes precedence over
  cancellation. Cancellation does not unload an operator-owned model.
- A successful load-command acknowledgement alone cannot establish readiness.
  Post-load inventory must contain the candidate; otherwise status is `BLOCKED`,
  resolution mode is `model_load_unverified` and `auto_load_performed` is false.
  `auto_load_attempted` is false when loading is disabled or unnecessary.

## Migration
1. Import pure identity functions, model/provider defaults, provider choices and target values from core.
   Existing runtime preparation functions retain their canonical application path.
   The runtime defaults module now owns environment observation only; its old
   constant imports have been migrated rather than adding a compatibility facade.
2. Read ordinary nested GGUF dictionaries through `target.to_payload()`; direct
   `target.gguf_models` entries are immutable `FrozenJson` values.
3. Supply the owning invocation's environment mapping when composing a provider;
   create a new client when adopting changed settings. Captured quarantine settings
   are admission inputs, not a live revocation mechanism for existing clients.
4. Treat `model_load_unverified` as blocked. Separate an attempted load from an
   observed loaded model and allow cleanup to finish after cancellation/timeout.

## Proof and limits
- `.tmp/c-provider-inputs/before.json` retains three failures: environment drift
  across real loopback HTTP/file discovery, a detached file worker after cancellation,
  and caller mutation of nested target evidence. The independent-export control passes.
- `.tmp/c-provider-inputs/load-before.json` retains two additional failures through
  real child CLI commands with a controlled executable: acknowledgement-only success
  and an attempt claimed when loading was disabled. This is not live LM Studio proof.
- Integration tests use real sockets/files/children, controlled worker barriers,
  explicit and concurrent settings, repeated cancellation, timeout and worker errors.
  The event-loop responsiveness bound is declared as 0.5 seconds and measured with
  the loop clock independently of timeout callback ordering.
- Complete provider composition, prompting/profile inputs, CLI executable/process
  environment capture, native-process policy, and shared-client concurrency/shutdown
  remain broader C/D work. The adapter's preparation dependency on application policy
  remains visible; no dependency exception or classification waiver is added.
- Historical host-clock and Linux approval/resume failures remain unresolved.
  Current source, package, installed and live evidence belongs in the canonical plan.

## Versioning
- Candidate core `0.6.8`; SDK remains `0.7.0a1`.
- Internal import/value changes, settings capture and corrected load observations
  require migration. Local work-hours commits do not establish release readiness.
