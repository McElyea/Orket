# Captured sandbox HTTP verification authority

## Summary
- Change title: Move sandbox HTTP execution out of core and compare captured expectations.
- Owner: Orket Core.
- Date: 2026-09-18.
- Affected contracts: sandbox HTTP verification, captured inputs, result interpretation, HTTP client ownership and fixture-runner import ownership.

## Delta
- Current behavior: Core performs HTTP and observes the clock. It ignores falsy expected values and reads mutable caller expectations after awaiting the response. Seven real loopback controls reproduce false passes on unchanged 0.6.15. Endpointless scenarios are silently omitted from pass/fail counts.
- Proposed behavior: Application captures immutable scenario/target values and explicit time, owns transport lifetime, and applies pure core interpretation after verified observation. Comparison includes every expected JSON value. Raw values must be JSON-compatible before model serialization; all captured scenario schemas validate before any batch request. Missing endpoints fail without HTTP; canonical JSON comparison does not coerce distinct types or numeric representations. Core no longer contains the fixture subprocess executable payload.
- Why this break is required now: Moving imports alone would preserve false verification and mutable admission. The C/D gate requires both pure core behavior and explicit, owned effects.

The durable contract is `docs/specs/SANDBOX_HTTP_VERIFICATION.md`. Core value clocks,
manifest file loading, schema-generated identities, broader async reachability,
adapter classification and remaining C/D/E/CAP obligations remain open.

## Migration Plan
1. Compatibility window: Internal imports migrate in the same checkpoint, without a core-to-application shim. Existing synchronous fixture tombstones retain their current removal ticket.
2. Migration steps: Compose `SandboxVerificationService`; provide scenario endpoints and exact expected JSON bodies, including null when null is intended. Import the native fixture payload from the execution adapter. Supply deterministic runtime inputs for controlled proof; real HTTP controls are not Docker deployment or model-inference proof.
3. Validation gates: Preserve the seven false-pass counterexamples; prove matching and mismatching falsy values, captured URL/body/expectations, invalid inputs, pure parity, real HTTP timeout/cancellation and repeated-cancellation cleanup under a predeclared 0.5-second responsiveness bound. Preserve the provider-admission controls after sharing their HTTP fixture. Run applicable source, installed, package and actual llama.cpp acceptance with retained adverse evidence.

## Rollback Plan
1. Rollback trigger: Captured comparison, request identity or owned cleanup cannot be preserved.
2. Rollback steps: Restore service, adapter, core values and callers together after owned requests settle. Keep false-pass observations; restored truthiness-based comparison is not accepted verification.
3. Data/state recovery notes: No historical result is rewritten. Previously reported sandbox passes do not retroactively gain captured-input or strict comparison proof.

## Versioning Decision
- Version bump type: Patch checkpoint destined for main, after required proof.
- Effective version/date: 0.6.16 local checkpoint, 2026-09-18.
- Downstream impact: Internal import migration and stricter HTTP result/admission behavior for all sandbox-verification callers. Full architectural-truth acceptance remains separate.
