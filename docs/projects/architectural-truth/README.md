# Architectural Truth

Last updated: 2026-10-03 (America/Denver)
Status: Active project registry
Owner: Orket Core

The [canonical plan](ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md) owns the ten-goal
ATG-v1 queue and resume record. **Eight goals are complete. Windows is the sole
acceptance target following the user's October 3 scope correction.**
The [worksets](GOAL_WORKSETS.json) retain the finite batches and evidence history.

Checkpoint **v0.6.142** removes Linux/WSL clock and hosted Gitea runner requirements
from this refactor. No infrastructure activation is needed to continue. Existing
portable code and CI definitions are unchanged; Linux/Mac support and a hosted
Quality pass are not claimed. The [pre-amendment plan](../archive/architectural-truth/AT10032026-WINDOWS-SCOPE/README.md)
preserves original outcomes and the retired requirements.

Windows Python 3.11/3.12 installed/public-path composites pass 6,236 cases each with
three unchanged Gitea opt-in skips. Actual llama.cpp library-flow proof remains
reusable at unchanged inputs. ATG-09 still needs current native Windows full-suite
verification with the unchanged 89% coverage floor after the reload repair; ATG-10
then reconciles and publishes the bounded result. Neither goal is newly complete.
The [two-day schedule](ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md#two-day-completion-plan)
now starts with Windows verification and has no runner-authorization dependency.

Worktree: `C:/Source/Orket-architectural-truth`.
Branch: `codex/architectural-truth-bt0`. No main merge is authorized.
Accepted BT-1 through BT-5 and A/B guarantees remain binding; new capability
admission and whole-lane retirement remain separate decisions.

Workflow: [Contributor Guide](../../CONTRIBUTOR.md).
Priority: [Roadmap](../../ROADMAP.md).
Exceptions: [register](ARCHITECTURE_EXCEPTION_REGISTER.json).
Earlier queue history: [archive](../archive/architectural-truth/AT10012026-GOAL-QUEUE/README.md).
