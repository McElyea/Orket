# Kernel publication input capture

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version/date: 0.6.57 candidate, 2026-09-20.
- Contract: `docs/specs/KERNEL_PUBLICATION_INPUTS.md`.

## Delta
The async kernel facade and control-plane publisher currently reread borrowed
request, response and ledger dictionaries after repository waits. Retained SQLite
probes show a changed proposal stored under its earlier digest, a rejected commit
published as success, and closeout using a changed event timestamp. Public engine
probes also lose the admitted target's control-plane references after caller
mutation. Capture JSON inputs before the first effect or await at each boundary.

Use the existing immutable JSON codec, with operation-owned views for effects.
Unsupported object/non-finite payloads fail at capture before publication.
Stable JSON behavior and existing authority remain unchanged. Move the existing
run/attempt/resource consistency checks to the resource lifecycle owner with the
same error type and messages, keeping the oversized publisher smaller.

## Migration and rollback
Valid JSON callers need no migration. Callers must submit a new invocation to
change inputs; editing borrowed objects does not change an admitted invocation.
Rollback reintroduces mixed authority observations and must disclose that limit.
Do not rewrite historical snapshots or receipts. Existing transaction and
kernel-ledger durability limitations remain in force.

## Versioning and verification
Compatible patch for the JSON contract; no durable schema change or new trust
boundary. Retain failing probes and prove corrected direct and public paths with
actual SQLite, then run affected source/installed regressions and exact package
binding. Remaining D/E/CAP and whole-lane acceptance stay open.
