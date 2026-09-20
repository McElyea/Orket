# Captured sandbox policy inputs

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.49 candidate, 2026-09-20.
- Durable contract: `docs/specs/SANDBOX_POLICY_INPUTS.md`.

## Delta and migration
Sandbox policies previously borrowed mutable allocator and runtime Sandbox
records, and selected policy/secret observations could change across preflight
awaits. Custom implementations now accept tech-stack strings, `SandboxPortInput`
and `SandboxComposeInput` from `core.contracts.decision_inputs`. Read declared
facts instead of changing runtime state or accessing workspace/container fields.
Plain-string recommendations are required; there is no old-signature retry.
Creation captures the policy, clock and both secrets before its first await.
Constructor environment selection uses the supplied environment snapshot.

Pre-admission policy failure releases its new in-memory allocation without
rewinding the allocator counter. Later compose refusal preserves durable
publications and the existing starting/reconciliation flag. This is not an atomic
rollback or an untrusted-code boundary. Existing lifecycle and credential behavior
otherwise remains unchanged; supported default output bytes are preserved.

## Verification and rollback
Retain pre-change mutation, allocation-leak and held-preflight counterexamples,
published .48 synthetic output hashes, strict input/refusal regressions and actual
SQLite publication checks. Verify affected source and installed callers, then
real Docker/HTTP creation and same-execution cleanup. Record actual observations
and unresolved platform/whole-suite limits in the canonical plan.

Rollback projections, application callers and custom strategies together. Do not
rewrite historical lifecycle, reservation or effect evidence. Fresh secret values
are excluded from proof records.

## Versioning decision
- Patch remediation checkpoint with an explicit breaking sandbox-policy API delta.
- Other D boundaries, E/CAP acceptance and explicit lane acceptance remain open.
