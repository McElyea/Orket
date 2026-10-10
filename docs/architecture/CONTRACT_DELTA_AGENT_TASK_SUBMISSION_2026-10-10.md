# Contract Delta: Public Governed Report Submission

## Summary
- Change title: Consume SDK task submissions with host-owned report verification.
- Owner: Orket Core.
- Date: 2026-10-10.
- Affected contracts: `GOVERNED_AGENT_LOOP_V1.md`, new
  `GOVERNED_AGENT_TASK_SUBMISSION.md`, governed-agent inspection projection.

## Delta
- Current behavior: Low-level submission accepts an iteration request and
  caller-authored lifecycle timestamps; its default verifier is ticket-specific.
- Proposed behavior: Add `agent run` using the existing SDK submission and
  materialized-input contracts. The host owns lifecycle construction and admits
  `structured_report.v1`. Inspection exposes retained advisory proposal text.
- Why now: Independent report workloads need a public entrypoint and an honest
  acceptance contract without taking over runtime, tool or terminal authority.

## Migration Plan
1. Compatibility window: Existing submit, ticket demo and wake/API routes keep
   their behavior. No SDK wire schema changes or import compatibility shims.
2. Migration steps: External report authors adopt the new submission policy,
   report shape and example. A Gardener adapter materializes selected evidence;
   it does not receive a shell or a repository-write capability from this path.
3. Validation gates: Public CLI/child/HTTP/SQLite tests, refusal and native input
   ownership controls, existing submission regressions, and actual local-model
   command/inspection/replay proof. Quality taxonomy, dependency direction and
   current-authority checks also apply.

## Rollback Plan
1. Rollback trigger: False completion, ownership regression or incorrect admission.
2. Rollback steps: Withdraw `agent run` admission while retaining inspection and
   replay of recorded evidence. Restore the prior authoring guidance.
3. Data/state recovery notes: Existing stores and wire versions remain readable;
   do not delete uncertain runs or silently redispatch them.

## Versioning Decision
- Version bump type: Additive host feature; no SDK schema bump.
- Effective version/date: Unreleased after 0.8.0, 2026-10-10.
- Downstream impact: Consumers may opt into the report contract. Successful
  delivery is not factual or repository-change verification.
