# Runtime architecture policy input boundary

Date: 2026-09-22
Status: Scoped implementation; acceptance evidence and remaining work live in the canonical plan
Canonical contract: [Runtime architecture policy inputs](../specs/RUNTIME_ARCHITECTURE_POLICY_INPUTS.md)
Canonical acceptance: [Architectural-truth remediation plan](../projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md)

The remaining D2 route evaluates architecture policy by rereading process environment
and readiness-report files inside synchronous helpers called by async settings and
orchestrator context paths. Separate calls can use different observations, and report
reads can block the request loop.

The replacement boundary separates immutable policy values from application observation.
Pure evaluators require explicit snapshots. Async observation retains its worker;
native observation refuses event-loop entry. Settings take one observation per request
while preserving operator changes between requests, precedence, output schema and
conditional-write conflicts. Orchestrator construction receives one explicit architecture
snapshot shared by mode resolution and allowed-pattern context.

Migration is required for direct policy-helper and orchestrator callers: supply the
appropriate immutable snapshot. No compatibility forwarding or hidden-context fallback
is introduced. Existing report normalizers and readiness criteria remain authoritative.
No model/provider behavior, capability admission, Linux acceptance or lane retirement
is authorized by this scoped input-boundary change.
