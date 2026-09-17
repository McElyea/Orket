# Retained Epic Preparation and Export Uncertainty

## Summary
- Change title: Retain preparation inputs before local closeout and external export.
- Owner: Orket Core.
- Date: 2026-09-12.
- Affected contracts: `CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`, standard Python
  `run_epic`/`run_card` reentry, Gitea export binding and runtime failure events.

## Delta
- Opening behavior: control-plane, receipt and summary failures occur before a
  ready publication plan exists. Same-session restart cannot finish this work
  without resetting cards or rejecting recovery. Export errors can be swallowed.
- Required behavior: application authority retains `epic_preparation.v1` inputs,
  policy, non-secret export binding and stage outputs before those operations.
  Preparation completion and ready-plan insertion commit in one journal transaction.
  Pending local preparation resumes before workload dispatch. Receipt, summary-write
  and export failures propagate; explicit degraded summary generation remains separate.
- Requests now bind full epic/team/environment definitions and build identity.
  Different builds or changed definitions cannot reuse retained work. Old records
  with insufficient bindings reject reentry rather than borrowing current inputs.
- Enabled exports retain an attempt marker before invoking the callback. Unknown
  results reject fresh reentry with `E_EPIC_EXPORT_OUTCOME_UNCERTAIN`, without
  automatic retry or success publication. Export target settings and date are
  retained; credential-bearing URLs reject construction and secrets stay out of
  the binding. Receipt recovery and remote reconciliation remain required work.

## Migration Plan
1. Add `epic_preparations` to the existing publication journal. Existing publication
   rows and their digests are unchanged; no historical inputs are invented.
2. Preserve the journal, committed WAL content, other runtime stores and acceptance
   evidence. Same-session reentry requires sufficient original bindings. A new
   execution uses a new session; this is not a repair for an uncertain old export.
3. Validate local failures, native process interruption, negative request drift,
   enabled-export uncertainty and live accepted-work recovery without model redispatch.
   Local effect probes do not establish Gitea acceptance. Initial preparation
   retention, custom writers and cross-installation recovery remain gated.

## Rollback Plan
1. Trigger: preparation recovery redispatches accepted work, loses retained inputs,
   retries an uncertain export or publishes unsupported success.
2. Reject affected reentry and repair the protocol while retaining original evidence.
   Do not clear the journal, backfill bindings or restore swallowed export failures.
3. Preserve remote evidence for later reconciliation; uncertainty is not a receipt
   that the effect happened or did not happen.

## Versioning Decision
- Effective date: 2026-09-12; additive internal `epic_preparation.v1` retained schema.
- No release/version bump or production migration is performed in this worktree.
- Callers must preserve exact same-session request definitions and handle explicit
  preparation failure or export uncertainty. No global atomicity or exactly-once
  external-effect guarantee is introduced.
