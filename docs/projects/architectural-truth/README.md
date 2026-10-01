# Architectural Truth

Last updated: 2026-10-01 (America/Denver)
Status: Active project registry
Owner: Orket Core

The [executable goal queue](ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md) is the single
canonical implementation plan and the file to target for continuing goal execution.
It defines ten fixed goals, dependencies, starting and exit criteria, evidence
requirements, exclusions and a resume record. **ATG-01/02/03/04 are published through v0.6.121;
ATG-05 is in progress.** Larger goals use bounded
batches without replacing the user's objective. The [workset inventory](GOAL_WORKSETS.json)
binds current sources, retained proof and pending batch IDs without creating a second plan.

The branch is `codex/architectural-truth-bt0` in
`C:/Source/Orket-architectural-truth`. Published `v0.6.117` closes the eight fixture
failures after the logging migration. Its complete source run records 11,584 passes,
zero failures and 93 skips, with 87.035153% coverage against the unchanged 89% gate.
The full evidence and proof limits are summarized in the queue.

The [history archive](../archive/architectural-truth/AT10012026-GOAL-QUEUE/README.md)
preserves the former plan and registry without discarding their observations.
The [September WIP checkpoint](../archive/architectural-truth/AT09302026-WIP-CHECKPOINT/CHECKPOINT.md)
retains the six unapplied proposal bundles. History and proposed CAP work do not
authorize extra queue goals. Accepted BT-1 through BT-5 guarantees remain binding;
whole-lane acceptance, a main merge and new capability admission remain separate.

Workflow authority: [Contributor Guide](../../CONTRIBUTOR.md).
Execution priority: [Roadmap](../../ROADMAP.md).
Current exception inventory: [register](ARCHITECTURE_EXCEPTION_REGISTER.json).
