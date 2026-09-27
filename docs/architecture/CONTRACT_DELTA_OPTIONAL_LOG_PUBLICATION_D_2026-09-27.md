# Optional event publication on the existing log writer

## Summary

- Owner: Orket Core, architectural-truth D.
- Date: 2026-09-27.
- Contract: `docs/specs/LOG_WRITE_SETTLEMENT.md`.
- Scope: five retained optional-publication caller-loop failures; native inline
  publication, audit settlement and API registration ownership remain authoritative.

## Delta

Event-loop calls previously performed first directory resolution/creation,
standard handlers and subscribers inline. Nested caller values remained borrowed.
The facade now detaches the same exact built-in domain used by required API events
and admits native main/artifact steps to the existing bounded FIFO and daemon.
One event carries its captured lexical workspace, options, timezone and subscriber
tokens through those steps. Record/runtime-envelope construction uses the same
native builder as inline calls; timezone resolution and sampling happen natively.

Main and artifact remain separate bounded admissions with exact per-path drops.
A dropped main suppresses its handler/subscriber attempts, while an accepted
artifact remains an independent attempt. A dropped artifact preserves accepted
main delivery attempts. All remaining untransferred tokens release on terminal
stage completion, total drop or daemon failure. An API callback that transferred
its token still owns the later acknowledgement under the existing API contract.

Overflow diagnostics move off-loop and use one bounded pending slot. Sparse
threshold notifications may coalesce while the writer is held; the counter stays
exact. No additional queue, executor, daemon, retry or writer restart is added.
`OSError` appends remain optional. Other deferred-stage failures retain fatal
writer identity and cause, so the native append frontier and tool audit refuse
rather than treating an unexpected failed append as successful settlement.
Handler and main-directory preparation failures also remain fatal, even when
their exception is `OSError`; append best effort does not authorize that fallback.
Optional subscriber-failure diagnostic appends retain the same `OSError` best
effort, so later subscriber attempts and their tokens continue to settlement.
The diagnostic's timestamp and standard-handler failures remain fatal. The native
required path still propagates its diagnostic append failure unchanged. An isolated
counterexample and its corrected positive/negative controls are retained with the
quality-checker review evidence under `.tmp/goal-20260927-quality/`.

## Migration Plan

1. Loop callers supply exact strings, ordinary built-in payload values and an exact
   native `Path`. Unsupported custom objects refuse without calling their hooks.
   The existing native/direct compatibility path remains synchronous.
2. Required API and other retained native workers keep their publication and error
   ownership. This change does not convert those operations into optional writes.
3. Preserve the six original opening assertions, audit/fatal/frontier guards and
   API handoff controls. Add capture refusal, physical main/artifact/subscriber
   readback, independent admission, real bounded overflow, fatal queued-token and
   process-reaping controls. Installed and broader acceptance belong to the plan.

## Rollback Plan

1. Lost tokens, queue-capacity drift, hidden fatal failure or altered required
   error precedence block acceptance.
2. Correct the shared queue/admission boundary and retain failed observations;
   do not add a second writer, weaken the opening bounds or mask audit failures.
3. Optional records already written remain partial effects. No rollback, atomic
   multi-sink delivery, crash durability or deadline is promised.

## Versioning Decision

- Patch successor to the published 0.6.106 checkpoint; release metadata is owned
  by the parent integration change.
- Event schema stays unchanged. Optional return now precedes native handler and
  subscriber execution; call return is admission only, never delivery proof.
- The public append-frontier claim remains prior accepted append-attempt settlement;
  incidental waiting for queued stages does not extend it to API handoff delivery.

## Remaining scope and proof ceiling

This bounded correction leaves the existing relative-root cwd capture, ambient
policy selection and lazy thread startup at admission. It does not establish
complete logging preparation or whole-entry D3. Per-application captured authority,
canonical preparation wiring, the remaining required-publication migrations and
legacy opaque tool-result admission remain separate obligations in the active plan.
Source/installed acceptance is recorded there, not inferred from this contract.
