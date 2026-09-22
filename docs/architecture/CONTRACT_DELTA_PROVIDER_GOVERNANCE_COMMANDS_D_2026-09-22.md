# Provider inventory and governance native command ownership

Date: 2026-09-22
Status: Scoped implementation; acceptance evidence and remaining work live in the canonical plan
Canonical contract: [Provider and governance command ownership](../specs/PROVIDER_GOVERNANCE_COMMAND_OWNERSHIP.md)
Canonical acceptance: [Architectural-truth remediation plan](../projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md)

The .86 source inventory identifies raw subprocess.run in provider CLI inventory and
raw async subprocess/communicate in Packet 1 alias commands. Native guards and parent
waiters do not establish descendant cleanup. The existing OS command owner must own
these paths, with finite budgets and explicit refusal on incomplete capture or cleanup.

Preserve return shapes, parsing, native refusal, observed model-load semantics and
alias ownership. No alternate process supervisor, provider substitution or permissive
fallback is introduced. Bounded output and governed command deadlines become explicit
admission constraints. Native worker cancellation retains its command until completion
or its admitted deadline; cleanup failure cannot become clean cancellation.

Process cleanup is not rollback of daemon-side effects or actual-provider acceptance.
Alias races, interrupted copy ambiguity, Linux clock instability, complete D/E/CAP and
explicit user acceptance remain separate work in the canonical plan.
