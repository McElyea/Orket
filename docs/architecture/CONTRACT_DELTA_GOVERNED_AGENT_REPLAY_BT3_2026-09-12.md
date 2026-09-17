# Governed-agent scoped replay contract delta

## Summary

- Change title: Require complete retained continuation evidence before reporting a replay match.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `GOVERNED_AGENT_LOOP_V1.md`, governed-agent replay API/CLI,
  SQLite decision publication, and `CURRENT_AUTHORITY.md`.
- Status: Scoped SD-02 replay acceptance passed within active BT-3; card
  completion and full BT-3 acceptance remain open.

## Delta

- Previous behavior compared surviving invocation rows, used repositories that
  could initialize storage while reading, and retained no input digest. A
  missing middle or tail snapshot could disappear from the comparison.
- V2 reads run/attempt/step/iteration/final-truth evidence in one read-only SQLite
  transaction. Canonical iteration steps supply the expected inventory. The
  application validates identity, evidence digests, typed inputs and completeness
  before reapplying the existing pure continuation function.
- The response includes scope, expected/snapshot/compared/matched counts and
  diagnostics. Empty intact histories remain `no_decisions`; missing evidence
  is `insufficient_evidence`; invalid evidence is `mismatch`. Only a complete,
  matching comparison returns CLI success. No provider, tool, effect or objective
  verification claim follows from a match.
- The claim is local record consistency. Coordinated privileged rewriting of
  the entire database cannot be detected without an independent historical anchor.
- Acceptance exposed a pre-existing Python 3.12 POSIX import-hook recursion:
  constructing `Path` during caller inspection imports `ntpath` and reenters the
  hook. Thread-local state now bounds only the hook's own origin inspection,
  resets before extension loading, and preserves declared-stdlib/host-module
  denial on the original and other threads. This is not an OS containment gate.

## Migration Plan

1. The API/CLI replay payload changes to `governed_agent_replay.v2`; consumers
   must handle the new status and nullable expected count. No V1 success fallback.
2. Normal store initialization serializes addition of nullable
   `decision_inputs_digest`. New publication records the digest in the same
   transaction as inputs and decision. Old rows remain null, including through
   initialization and idempotent publication; historical evidence is not resealed.
3. Replay opens existing stores read-only and never triggers migration. Missing
   columns, malformed rows, missing steps and missing snapshots fail closed.
4. Validation uses real SQLite stores, CLI and authenticated API requests,
   concurrent mutation, legacy initialization, real child processes and live
   llama.cpp evidence. Proof status and exact results live in the active plan.

## Rollback Plan

1. A regression in valid comparisons blocks BT-3 acceptance.
2. Preserve affected stores and evidence, repair the V2 reader or publication
   boundary, and rerun the counterexamples. Do not restore the surviving-subset
   success rule as a fallback.
3. The nullable column is additive; older writers may leave new inputs unsealed.
   Retain the column and raw rows. Such rows remain insufficient for V2 replay;
   rollback does not justify manufacturing historical digests.

## Versioning Decision

- Payload version: `governed_agent_replay.v2`.
- Effective date: 2026-09-12, active worktree candidate.
- Core remains 0.6.2 until an authorized versioned commit/release step. No SDK
  request/result wire version changes, commit, tag, push or store activation.
- Downstream impact: API/CLI consumers must surface incomplete evidence and
  distinguish continuation comparison from verified workload completion.
