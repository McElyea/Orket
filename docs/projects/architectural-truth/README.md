# Architectural Truth

Last updated: 2026-10-01 (America/Denver)
Status: Active project registry
Owner: Orket Core

The [executable goal queue](ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md) is the single
canonical implementation plan and the file to target for continuing goal execution.
It defines ten fixed goals, dependencies, starting and exit criteria, evidence
requirements, exclusions and a resume record. **ATG-01/02/03/04/05/06/07 are published through v0.6.124;
ATG-08 fresh Windows package proof passes; v0.6.125 publication is pending.** Larger goals use bounded
batches without replacing the user's objective. The [workset inventory](GOAL_WORKSETS.json)
binds current sources, retained proof and pending batch IDs without creating a second plan.

The branch is `codex/architectural-truth-bt0` in
`C:/Source/Orket-architectural-truth`. Published `v0.6.117` closes the eight fixture
failures after the logging migration. Its complete source run records 11,584 passes,
zero failures and 93 skips, with 87.035153% coverage against the unchanged 89% gate.
The preserved baseline and proof limits are summarized in the queue. ATG-07's
[closeout](../archive/architectural-truth/AT10012026-ATG07/CLOSEOUT.md) now records
12,964 passes, zero failures, 93 skips and 89.213132% coverage with unchanged source
inputs. ATG-08's [closeout](../archive/architectural-truth/AT10012026-ATG08/CLOSEOUT.md)
records fresh Windows Python 3.11/3.12 installed selections: each has 6,231 passes,
zero failures and three unchanged Gitea opt-in skips, with package and input identity
preserved. Fresh Linux/provider/hosted proof remains open.

The [history archive](../archive/architectural-truth/AT10012026-GOAL-QUEUE/README.md)
preserves the former plan and registry without discarding their observations.
The [September WIP checkpoint](../archive/architectural-truth/AT09302026-WIP-CHECKPOINT/CHECKPOINT.md)
retains the six unapplied proposal bundles. History and proposed CAP work do not
authorize extra queue goals. Accepted BT-1 through BT-5 guarantees remain binding;
whole-lane acceptance, a main merge and new capability admission remain separate.

Workflow authority: [Contributor Guide](../../CONTRIBUTOR.md).
Execution priority: [Roadmap](../../ROADMAP.md).
Current exception inventory: [register](ARCHITECTURE_EXCEPTION_REGISTER.json).
