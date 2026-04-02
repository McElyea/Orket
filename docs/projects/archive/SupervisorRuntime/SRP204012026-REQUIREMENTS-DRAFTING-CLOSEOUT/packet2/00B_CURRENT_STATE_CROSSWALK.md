# SupervisorRuntime Packet 2 Current-State Crosswalk
Last updated: 2026-04-01
Status: Completed archived draft current-state honesty
Owner: Orket Core
Packet role: Crosswalk

## Status terms

1. `aligned` - already broadly matches the intended Packet 2 direction
2. `partial` - meaningful implementation exists, but default-path convergence is incomplete
3. `hybrid` - multiple authority regimes still coexist
4. `draft-only` - Packet 2 names the family, but current authority is not yet packet-shaped

| Surface family | Current status | Current truthful note | Packet 2 target |
| --- | --- | --- | --- |
| Principal model | `draft-only` | Principal roles are implied across current docs and services, not yet one packet authority family. | One explicit principal model shared by runtime, operator, scheduler, extension, and client surfaces. |
| Capability kernel | `hybrid` | Capability and approval semantics exist, but remain fragmented across safe-tooling, operator, and control-plane seams. | One named capability kernel with caller, scope, timeout, approval, and audit rules. |
| Admission and execution identity | `partial` | Canonical run or attempt or step publication is real on many paths, but not yet one Packet 2 admission family. | One admission and identity story across governed runtime, replay, and artifacts. |
| Resource, namespace, and ownership | `partial` | Reservation, lease, and resource truth are real on strong paths, but not universal default-path behavior. | One default-path ownership and namespace boundary. |
| Effect journal and mutation authority | `partial` | Effect journal publication is real, but older reconstructed effect and closure surfaces still survive. | One normative mutation and closure-relevant write path. |
| Checkpoint, recovery, and resume | `partial` | Checkpoint and recovery records exist on bounded paths, but not as universal Packet 2 authority. | One explicit supervisor-owned recovery family. |
| Operator control and approvals | `partial` | Approval and operator-action surfaces are real, but broader operator control is not yet one packet family. | One operator command, risk, and attestation authority family. |
| Reconciliation and final truth | `partial` | Reconciliation and final-truth publication exist on selected paths, but closure is still partly hybrid. | One explicit divergence and terminal-truth family. |
| Public control surfaces | `hybrid` | API and inspection surfaces exist, but not yet as one Packet 2 public control contract. | One coherent runs, approvals, replay, and evidence posture. |
| Extension and client boundary | `aligned` | Current direction already keeps runtime authority in the host and clients thin. | Preserve and formalize the thin-client rule. |
| Scheduler and triggered runs | `partial` | Scheduling and triggered execution exist, but not yet as one explicit Packet 2 trigger model. | One trigger-class posture under the same host-owned control plane. |
