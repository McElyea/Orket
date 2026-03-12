# Docker Sandbox Lifecycle Implementation Plan

Last updated: 2026-03-11
Status: Active implementation plan
Owner: Orket Core
Requirements authority: `docs/projects/Docker/01-REQUIREMENTS.md`
Lane type: Maintenance (Non-Priority), finite reliability implementation

## 1. Objective

Implement a durable, fail-closed Docker sandbox lifecycle system that is:
1. deterministic
2. race-safe
3. host/context-scoped for destructive authority
4. verifiable with live Docker proof

The implementation must satisfy all normative requirements in `01-REQUIREMENTS.md`.

## 2. Scope

In scope:
1. durable lifecycle state and policy versioning
2. lifecycle mutation engine with CAS fencing and operation idempotency
3. reconciliation and sweeper cleanup execution
4. unknown-outcome handling and requires-reconciliation gating
5. operator-safe cleanup authority and audit-safe eventing
6. test and CI leak-proof gates

Out of scope:
1. queue-platform replacement
2. generic cleanup for non-Orket Docker projects
3. UI redesign beyond required lifecycle visibility fields

## 3. Execution Principles

1. Fail closed on missing lifecycle authority.
2. Never claim cleanup success from command return code alone.
3. Treat Docker as observed truth and lifecycle store as authority truth; reconcile explicitly.
4. Use smallest vertical slices with proof at the highest practical layer.
5. Keep destructive cleanup bounded to confirmed authority scope only.

## 4. Phase Plan

### Phase 0 - Spec-to-Test Harness (Required First)

Deliverables:
1. lifecycle transition matrix harness derived from requirement transition table
2. forbidden-transition checks and monotonicity checks
3. CAS contention simulation for cleanup claim and lease-owner writes
4. reconciliation matrix contract tests (including partial presence cases)

Required proof:
1. `Layer: contract` transition and reconciliation suites
2. `Layer: unit` targeted edge cases (version mismatch, payload hash mismatch, stale owner)

Exit criteria:
1. harness fails against current behavior where requirements are missing
2. harness is stable and used as implementation gate for later phases

### Phase 1 - Durable Authority Model

Deliverables:
1. lifecycle record schema with required fields:
   - `schema_version`, `policy_version`
   - `cleanup_failure_reason`
   - `requires_reconciliation`
   - `docker_context`, `docker_host_id`
2. durable stores for:
   - lifecycle records
   - operation-id dedupe
   - lifecycle/integrity events
3. schema-version compatibility checks and policy-version interpretation paths

Required proof:
1. `Layer: contract` persistence schema contract tests
2. `Layer: integration` storage read/write and version-compat behavior

Exit criteria:
1. lifecycle writes are authoritative and version-aware
2. unsupported future schema records are rejected per contract

### Phase 2 - Lifecycle Engine + Idempotency

Deliverables:
1. lifecycle mutation service with CAS guards for state/cleanup/ownership mutations
2. `operation_id` enforcement for required operations
3. dedupe store behavior:
   - unseen `operation_id` executes
   - duplicate same payload returns prior result
   - duplicate different payload rejects with integrity event
4. unknown-outcome state handling and `requires_reconciliation` gating

Required proof:
1. `Layer: contract` operation-id and dedupe behavior
2. `Layer: integration` crash/retry idempotency checks

Exit criteria:
1. duplicate destructive operations cannot execute twice
2. unknown outcomes remain blocked until deterministic reconciliation

### Phase 3 - Reconciler and Cleanup Orchestrator

Deliverables:
1. startup + periodic reconciliation using closed matrix classification
2. orphan classification and promotion logic (verified vs unverified)
3. cleanup scheduler and claimant with CAS-safe claim transition
4. cleanup executor with authority checks:
   - lifecycle record or ownership markers
   - host/context match required
5. cleanup verification against observed/planned inventory
6. runtime recovery for indeterminate create/cleanup outcomes
7. terminal outcome export path that persists required evidence outside sandbox-managed Docker resources before durable terminal claims

Required proof:
1. `Layer: contract` reconciliation and authority matrix tests
2. `Layer: integration` real Docker cleanup verification tests
3. `Layer: end-to-end` unknown-outcome reconciliation after induced failure

Exit criteria:
1. cleanup decisions are deterministic and auditable
2. cleaned classification is only set after live absence verification

### Phase 4 - Eventing, Fallback, and Failure Visibility

Deliverables:
1. canonical event schema implementation with required fields
2. severity routing policy implementation and thresholds
3. durable event fallback path:
   - local spool
   - syslog/journald
   - stdout/stderr
4. total-sink-failure fatal marker behavior
5. spool replay into canonical store with idempotency and metadata preservation
6. structured cleanup decision and execution-result events with dry-run vs execute visibility

Required proof:
1. `Layer: integration` fallback + replay behavior
2. `Layer: integration` all-sink-failure fail-closed scenario

Exit criteria:
1. no silent failure path remains for critical lifecycle errors
2. destructive actions remain blocked when authority/event guarantees are unavailable

### Phase 5 - Interfaces and Operator Surfaces

Deliverables:
1. API/operator surfaces expose required lifecycle fields
2. operations blocked while `requires_reconciliation=true`
3. structured cleanup/error visibility without hidden in-memory-only state

Required proof:
1. `Layer: contract` API field-shape and policy checks
2. `Layer: integration` durable operator-view and conflict-path behavior

Exit criteria:
1. operator view reflects durable lifecycle truth without hidden state

### Phase 6 - CI Gates and Live Verification

Deliverables:
1. test default: sandbox disabled unless explicitly required
2. CI leak checks implemented in `.gitea/workflows/quality.yml`:
   - label-based (`orket.managed=true`)
   - prefix-based (`orket-sandbox-*`) with explicit allowlist
3. live acceptance scenarios for:
    - cross-daemon cleanup rejection
    - unknown-outcome recovery after induced failure
    - orphan discovery with verified vs unverified classification
    - scheduled cleanup sweep execution
    - terminal evidence export plus policy-driven sweep cleanup
    - fail-closed store outage at the orchestrator boundary
    - cleanup-claim race fencing
    - sweeper crash between delete and verify
    - leak-proof post-run verification

Required proof:
1. `Layer: integration` + `Layer: end-to-end` runs with observed results recorded as:
   - primary
   - degraded
   - blocked

Exit criteria:
1. acceptance criteria in `01-REQUIREMENTS.md` are demonstrated with live evidence
2. no orphaned test-created sandbox projects remain after CI run

## 5. Work Breakdown

Implementation order:
1. Phase 0 and Phase 1 (authority foundation)
2. Phase 2 (mutation correctness + idempotency)
3. Phase 3 (reconciliation and cleanup execution)
4. Phase 4 and Phase 5 (visibility and resilience)
5. Phase 6 (live proof and gate hardening)

## 6. Verification and Evidence Expectations

For each phase, capture:
1. what changed
2. verification layer(s) executed (`unit`, `contract`, `integration`, `end-to-end`)
3. observed outcome (`success`, `failure`, `partial success`, `environment blocker`)
4. exact blocker/error when not successful

Live Docker verification is mandatory for cleanup correctness claims.

### Canonical Evidence Root

All implementation evidence for this lane must be stored under a single canonical evidence root.

Canonical base path:
1. `docs/projects/Docker/evidence/`

Recommended phase subpaths:
1. `docs/projects/Docker/evidence/phase-0/`
2. `docs/projects/Docker/evidence/phase-1/`
3. `docs/projects/Docker/evidence/phase-2/`
4. `docs/projects/Docker/evidence/phase-3/`
5. `docs/projects/Docker/evidence/phase-4/`
6. `docs/projects/Docker/evidence/phase-5/`
7. `docs/projects/Docker/evidence/phase-6/`

Rules:
1. Every traceability `Evidence Path` must resolve beneath the canonical evidence root.
2. Evidence locations outside the canonical root are non-compliant unless explicitly approved by lane policy.
3. Phase evidence should use stable subpaths so later updates append rather than relocate prior proof.

## 7. Definition of Done

This lane is complete when:
1. all acceptance criteria from `01-REQUIREMENTS.md` are proven
2. lifecycle state machine and reconciliation behavior are contract-locked
3. destructive cleanup is authority-safe, host/context-scoped, and idempotent
4. CI leak gates and fallback failure paths are green with truthful evidence

Canonicality Note

Phase sections define delivery order and implementation sequencing.

Sections 8-12 define cross-phase governance, including:
1. traceability
2. migration rules
3. multi-instance reconciliation ownership
4. idempotency versioning
5. reconciliation health requirements

When wording overlaps between a phase section and Sections 8-12, the cross-phase governance sections are canonical, unless a phase section explicitly declares itself the canonical source.

This note must appear only once in the document and must be referenced rather than duplicated elsewhere.

## 8. Requirement Traceability

| Requirement ID | Requirement Summary | Phase | Deliverable | Proof Layer | Test Reference | Evidence Path | Status |
|---|---|---|---|---|---|---|---|
| R1 | Durable lifecycle record and required fields | Phase 1 | Lifecycle schema + durable store | Contract, Integration | `tests/contracts/test_sandbox_lifecycle_schema_contract.py`; `tests/integration/test_sandbox_lifecycle_repository.py` | `docs/projects/Docker/evidence/phase-1/pytest-sandbox-lifecycle-schema-contract.txt`; `docs/projects/Docker/evidence/phase-1/pytest-sandbox-lifecycle-repository.txt` | Completed |
| R2 | Record creation ordering | Phase 1,3,6 | Fail-closed create path + recovery gating | Integration, End-to-end | `tests/integration/test_sandbox_orchestrator_lifecycle.py`; `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`; `tests/acceptance/test_sandbox_store_outage_fail_closed.py` | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-orchestrator-lifecycle.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-runtime-recovery-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-store-outage-fail-closed.txt` | Completed |
| R3 | Explicit terminal contract | Phase 2,3,6 | Lifecycle transitions + runtime terminalization + durable terminal evidence export | Contract, Integration, End-to-end | `tests/contracts/test_sandbox_lifecycle_contract.py`; `tests/contracts/test_sandbox_lifecycle_mutation_contract.py`; `tests/integration/test_sandbox_orchestrator_lifecycle.py`; `tests/integration/test_sandbox_terminal_outcome_service.py`; `tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py` | `docs/projects/Docker/evidence/phase-2/pytest-sandbox-lifecycle-mutation-contract.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-orchestrator-lifecycle.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-terminal-outcome-service.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-terminal-evidence-cleanup-live-docker.txt` | Completed |
| R4 | Policy-driven cleanup eligibility | Phase 2,3,5,6 | Policy engine + scheduler + reclaim/hard-max-age cleanup scheduling + deterministic dry-run and execute cleanup decisions | Contract, Integration, End-to-end | `tests/contracts/test_sandbox_lifecycle_reconciliation_contract.py`; `tests/contracts/test_sandbox_cleanup_decision_contract.py`; `tests/integration/test_sandbox_cleanup_scheduler_service.py`; `tests/integration/test_sandbox_runtime_recovery_service.py`; `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`; `tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py` | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-lifecycle-reconciliation-contracts.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-runtime-recovery-service.txt`; `docs/projects/Docker/evidence/phase-5/pytest-sandbox-cleanup-decision-contract.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-runtime-recovery-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-terminal-evidence-cleanup-live-docker.txt` | Completed |
| R5 | Lease and heartbeat semantics | Phase 2,6 | Mutation engine fencing + renewals + ownership reacquire | Contract, Integration, End-to-end | `tests/contracts/test_sandbox_lifecycle_mutation_contract.py`; `tests/core/test_sandbox_lifecycle_fencing.py`; `tests/integration/test_sandbox_lifecycle_mutation_service.py`; `tests/integration/test_sandbox_restart_policy_service.py`; `tests/acceptance/test_sandbox_restart_reclaim_live_docker.py` | `docs/projects/Docker/evidence/phase-2/pytest-sandbox-lifecycle-mutation-contract.txt`; `docs/projects/Docker/evidence/phase-2/pytest-sandbox-lifecycle-mutation-service.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-restart-reclaim-live-docker.txt` | Completed |
| R6 | Restart-loop and unhealthy classification policy | Phase 3,6 | Restart/unhealthy policy implementation + operator projection | Contract, Integration, End-to-end | `tests/contracts/test_sandbox_restart_policy_contract.py`; `tests/integration/test_sandbox_restart_policy_service.py`; `tests/acceptance/test_sandbox_restart_reclaim_live_docker.py` | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-restart-policy-contract.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-restart-policy-service.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-restart-reclaim-live-docker.txt` | Completed |
| R7 | Reconciliation and orphan handling | Phase 3,6 | Reconciliation engine + unknown-outcome recovery + orphan discovery + verified-orphan fallback cleanup | Contract, Integration, End-to-end | `tests/contracts/test_sandbox_lifecycle_reconciliation_contract.py`; `tests/integration/test_sandbox_lifecycle_reconciliation_service.py`; `tests/integration/test_sandbox_runtime_recovery_service.py`; `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`; `tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py`; `tests/acceptance/test_sandbox_restart_reclaim_live_docker.py` | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-lifecycle-reconciliation-contracts.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-lifecycle-reconciliation-services.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-runtime-recovery-service.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-runtime-recovery-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-orphan-reconciliation-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-restart-reclaim-live-docker.txt` | Completed |
| R8 | Cleanup authority and execution | Phase 3,6 | Authority checks + compose cleanup + label-scoped fallback cleanup executor | Contract, Integration, End-to-end | `tests/contracts/test_sandbox_cleanup_authority_contract.py`; `tests/integration/test_sandbox_orchestrator_lifecycle.py`; `tests/integration/test_sandbox_runtime_recovery_service.py`; `tests/acceptance/test_sandbox_orchestrator_live_docker.py`; `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`; `tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py`; `tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py` | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-orchestrator-lifecycle.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-runtime-recovery-service.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-orchestrator-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-runtime-recovery-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-orphan-reconciliation-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-terminal-evidence-cleanup-live-docker.txt` | Completed |
| R9 | Cleanup verification | Phase 3,6 | Verification service + live absence proof | Integration, End-to-end | `tests/integration/test_sandbox_cleanup_verification_service.py`; `tests/integration/test_sandbox_orchestrator_lifecycle.py`; `tests/acceptance/test_sandbox_orchestrator_live_docker.py`; `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`; `tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py` | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-orchestrator-lifecycle.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-orchestrator-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-runtime-recovery-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-terminal-evidence-cleanup-live-docker.txt` | Completed |
| R10 | Operator visibility | Phase 4,5 | Event schema + operator surfaces + cleanup decision visibility | Contract, Integration | `tests/contracts/test_sandbox_cleanup_decision_contract.py`; `tests/integration/test_sandbox_lifecycle_event_service.py`; `tests/integration/test_sandbox_lifecycle_view_service.py`; `tests/interfaces/test_sandbox_lifecycle_operator_api.py`; `tests/integration/test_sandbox_runtime_recovery_service.py` | `docs/projects/Docker/evidence/phase-4/pytest-sandbox-lifecycle-event-service.txt`; `docs/projects/Docker/evidence/phase-5/pytest-sandbox-cleanup-decision-contract.txt`; `docs/projects/Docker/evidence/phase-5/pytest-sandbox-lifecycle-view-service.txt`; `docs/projects/Docker/evidence/phase-5/pytest-sandbox-lifecycle-operator-api.txt`; `docs/projects/Docker/evidence/phase-3/pytest-sandbox-runtime-recovery-service.txt` | Completed |
| R11 | Test behavior requirements | Phase 6 | Acceptance gating + leak-proof cleanup evidence + CI leak gate wiring | Integration, End-to-end | `tests/integration/test_sandbox_orchestrator_lifecycle.py`; `tests/acceptance/test_sandbox_orchestrator_live_docker.py`; `tests/acceptance/test_sandbox_runtime_recovery_live_docker.py`; `tests/acceptance/test_sandbox_orphan_reconciliation_live_docker.py`; `tests/acceptance/test_sandbox_restart_reclaim_live_docker.py`; `tests/acceptance/test_sandbox_terminal_evidence_cleanup_live_docker.py`; `tests/acceptance/test_sandbox_cleanup_leak_gate.py`; workflow: `.gitea/workflows/quality.yml` (`sandbox_docker_acceptance`) | `docs/projects/Docker/evidence/phase-3/pytest-sandbox-orchestrator-lifecycle.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-orchestrator-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-runtime-recovery-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-orphan-reconciliation-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-restart-reclaim-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-terminal-evidence-cleanup-live-docker.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-cleanup-leak-gate.txt`; `docs/projects/Docker/evidence/phase-6/sandbox-leak-gate-local-check.txt` | In progress |
| R12 | Concurrency and fencing | Phase 0,2,3,6 | CAS contracts + cleanup claim fencing | Unit, Contract, Integration, End-to-end | `tests/core/test_sandbox_lifecycle_fencing.py`; `tests/contracts/test_sandbox_lifecycle_mutation_contract.py`; `tests/integration/test_sandbox_cleanup_scheduler_service.py`; `tests/acceptance/test_sandbox_cleanup_claim_race.py` | `docs/projects/Docker/evidence/phase-2/pytest-sandbox-lifecycle-mutation-contract.txt`; `docs/projects/Docker/evidence/phase-2/pytest-sandbox-lifecycle-mutation-service.txt`; `docs/projects/Docker/evidence/phase-6/pytest-sandbox-cleanup-claim-race.txt` | Completed |

TBD retirement rule

Once a phase enters active implementation, no traceability row mapped to that phase may retain `TBD` in either:
1. `Test Reference`
2. `Evidence Path`

Before implementation work for that phase is considered in progress, each mapped row must identify at minimum:
1. a concrete planned test identifier or suite name
2. a concrete planned evidence location under the canonical evidence root

A phase may not be marked active while its mapped traceability rows still contain unresolved `TBD` placeholders for required proof artifacts.

Traceability Maintenance Rule

Any commit that modifies:
1. phase scope
2. phase deliverables
3. proof expectations
4. requirement coverage

must update the affected traceability row or rows in the same commit.

A change to the implementation plan that alters requirement coverage without updating the traceability table is considered incomplete.

Plan hygiene gate

Documentation and CI hygiene must fail when a change affects a phase's scope, deliverables, proof expectations, or requirement coverage and the corresponding Section 8 traceability row or rows are not updated in the same change.

Minimum enforcement:
1. changed phase content requires matching traceability-row review
2. status, deliverable, proof layer, test reference, and evidence path must remain synchronized
3. unsynchronized plan and traceability changes are treated as incomplete work
