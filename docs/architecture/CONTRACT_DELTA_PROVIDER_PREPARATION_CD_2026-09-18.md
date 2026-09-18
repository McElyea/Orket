# Explicit application-owned provider preparation

## Summary
- Change title: Admit provider inference through explicit application preparation.
- Owner: Orket Core.
- Date: 2026-09-18.
- Affected contracts: local provider composition, preparation policy, target identity and captured endpoint defaults.

## Delta
- Current behavior: The LLM adapter imports application preparation and conditionally skips it based on client class/module names and mock-transport detection. An actual derived HTTP client reaches inference without inventory and despite provider quarantine. With an explicit empty environment, the Ollama client also inherits an excluded ambient host through the library default.
- Proposed behavior: `ProviderPreparationService` owns captured preparation settings and delegates to the existing runtime discovery/load authority. Application composition supplies the core `ProviderPreparationPort` to the adapter. Each uncached preparation consumes an immutable `ProviderPreparationRequest`; its admitted target must match provider, backend, requested model and normalized endpoint. Auto-selection may choose another admitted model, but cannot substitute another request or endpoint. A blocked target is not cached and cannot reach inference.
- Why this break is required now: Real loopback HTTP controls demonstrate the client-type policy bypass on unchanged 0.6.14. Removing the application import alone would preserve that false admission boundary.

The adapter no longer detects test transports or client class/module identities.
Isolated transport tests explicitly supply controlled preparation through the same
port. Raw adapter construction requires the port; normal callers retain the
application factory. Existing pinned-target validation remains in force and a
valid pinned target is not prepared again. Captured quarantine remains admission
input, not live revocation of an already admitted client.

Pure endpoint normalization and the Ollama default endpoint belong to
`orket/core/contracts/provider_runtime.py`. The Ollama transport receives an
explicit captured/default host. The observed constructor check covers actual
client configuration and cleanup; it is not live Ollama inference proof.

## Migration Plan
1. Compatibility window: Internal callers migrate in the same checkpoint; no adapter-to-application shim or client-type bypass remains.
2. Migration steps: Use `create_local_model_provider`, or explicitly supply both prompt and preparation ports to `LocalModelProvider`. Import `normalize_base_url` from the core provider contract. Test fixtures declare controlled admission instead of relying on implicit warmup suppression.
3. Validation gates: Real HTTP admission/quarantine controls for ordinary, derived and forwarding mock clients; rejected target identity, captured environment, inventory/load cancellation and provider/telemetry regressions. Fresh package, four installed cells and actual llama.cpp proof remain required in the canonical remediation plan.

The initial installed corpus also retains an unrelated stock-clock protocol
timestamp refusal. Its success fixture now supplies ordered time; real dual-ledger
controls retain and recover a refused mirror effect under backward supplied time.
These controls do not establish stock-clock reliability or the historical clock
movement's cause. The canonical plan retains the original failure and revised corpus.

## Rollback Plan
1. Rollback trigger: Preparation, selected-target identity or inference parity cannot be preserved.
2. Rollback steps: Restore factory, adapter, contracts and consumers together after settling active work; retain failed observations. Do not describe restored client-type bypass as acceptable admission.
3. Data/state recovery notes: No persisted schema or historical receipt rewrite is introduced. This change does not revoke a previously pinned target, unload an operator model or repair prior unprepared calls.

## Versioning Decision
- Version bump type: Patch checkpoint destined for main, with a local annotated tag after verification.
- Effective version/date: 0.6.15 local checkpoint, 2026-09-18.
- Downstream impact: Internal port/import migration. Complete CLI executable/process environment capture, concurrent first-preparation ownership, shared-client request lifetime/shutdown and remaining provider settings remain active C/D work. Controlled HTTP responses are not model-quality proof; no new provider promotion or hostile-code boundary is claimed.
