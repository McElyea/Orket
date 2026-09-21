# Kernel admission policy input capture

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.56 candidate, 2026-09-20.
- Contract: `docs/specs/KERNEL_POLICY_INPUTS.md`.

## Delta
Admission currently observes enablement before request processing and resolver/
pre-resolved flags later during decision evaluation. Concurrent operator changes
can mix those observations and reverse the decision. Capture one immutable
three-flag input before request validation or hashing and pass it explicitly to
the extracted decision evaluator. Keep existing decoding and default results.

Trusted Python callers gain an optional typed input. HTTP/request payloads gain
no override. Disabled selected input refuses before ledger publication. Existing
policy-digest fixtures, approval authority, events and ledger durability limits
remain unchanged. The larger runtime module shrinks by extracting the decision
function, with one canonical implementation.

## Migration and rollback
Default callers require no migration. Callers that want a retained selection
may construct an input from an explicit environment snapshot and pass it through
the optional kernel API keyword. Do not translate untrusted request fields into
that argument. Rollback restores mixed ambient observations and must disclose
that limitation; it must not rewrite earlier decisions or evidence.

## Versioning and verification
Compatible patch; no durable schema or authority expansion. Retain both observed
pre-change decision reversals, independent published-output parity and actual
public-path evidence. Remaining D/E/CAP and lane acceptance stay open.
