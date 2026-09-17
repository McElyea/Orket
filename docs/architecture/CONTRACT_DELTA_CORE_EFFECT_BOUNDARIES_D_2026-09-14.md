# Core failure and reconciliation effect boundaries

Owner: Orket Core
Date: 2026-09-14
Status: Implemented; installed gate retains a lease-clock failure; D not accepted

`FailureReporter.build_report(...)` now constructs a value from an explicit
timestamp and inputs. `PolicyViolationReport` no longer manufactures ambient time;
its JSON fields retain their meanings and roles serialize as a JSON array. The
application's `FailureReportService.publish(...)` owns the existing
`agent_output/policy_violation_<card_id>.json` artifact and saved event. Report
identity must be a portable file-name component. The event follows a completed,
closed file write. Publication retains its admitted I/O through cancellation.

Orchestrator composition accepts `failure_report_clock`; its default is the UTC
adapter in `orket/time_utils.py`. Failure handling supplies that timestamp to core.
This is an explicit input for failure reporting, not completion of D's remaining
runtime clock, identity, environment or decision-context migration.

Core `StructuralReconciler.plan(...)` consumes immutable structural-asset values
and returns immutable proposed writes, adoptions or problems. It performs no
traversal, writes or logging. The application service at
`orket/application/services/structural_reconciliation_service.py` owns snapshot
collection, policy invocation, storage updates and adoption events. Its synchronous
`reconcile_all()` entrypoint is for CLI/worker callers and refuses a running event
loop; async callers await `reconcile()`. Board and CLI startup retain their workers
through cancellation. Storage declares its side effects and runs filesystem work
in owned workers.

Malformed assets, invalid reference shapes and missing required adoption targets
fail explicitly before applying a plan. The previous behavior could report an
invalid issue adopted, retain no corresponding effect, and return without failure.
Adoption events now follow a verified target write. Each target is compared with
its captured content, replaced and read back; a changed target is refused. The
two target files do not form one transaction, and this change makes no claim of
fencing concurrent external board editors. A later write failure does not undo
earlier verified writes or their truthful events.

Epic identity remains global by name. Where departments contain the same epic
name, reconciliation selects one adoption in sorted department order. This makes
selection deterministic while preserving the existing single-adoption rule.
Legacy issue filename/payload identity mismatches are not newly normalized.

Migration is explicit: callers of core `FailureReporter.generate_report(...)`
must construct a value and use the application publisher. Callers constructing
core `StructuralReconciler` for filesystem effects must use the application
service. No core-to-application forwarding shim is added. Deprecated domain
module aliases continue to expose core values; they do not restore removed effect
methods. There is no runtime-store migration, release/version/tag action or
artifact deletion in this change.

ToolGate now has the same separation. The application implementation at
`orket/application/services/tool_gate_service.py` owns path resolution and
AST/iDesign validation in a retained worker, then supplies immutable
`FileWriteFacts` to synchronous core policy. Missing facts fail closed. The
transient iDesign view has an explicit non-temporal timestamp and is never
published as execution evidence. The runtime's async `validate(...)` surface is
preserved by the application implementation and existing service import. Direct
core callers must now supply facts to the pure synchronous policy. Governed file
adapters require an injected `ToolGateValidator`; they cannot construct
application authority. The canonical tool-execution gate spec records the new
composition path. Original error categories and ordering are retained.

Proof must cover deterministic value parity, real saved artifacts and adoption
state, malformed-input refusal, changed-target refusal, event ordering and owned
cancellation with a responsiveness limit fixed before measurement. Source and
installed package proof remain separate. D1's three boundaries are implemented.
The affected source gate passes; three installed cells pass, while Linux 3.11
retains one issue-closeout lease-clock refusal. Its cause remains unestablished.
The canonical plan records current evidence and limits; remaining core effects
and the wider C/D/E/capability gates remain open.
