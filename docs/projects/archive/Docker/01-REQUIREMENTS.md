# Docker Sandbox Lifecycle Requirements

Last updated: 2026-03-12
Status: Archived requirements baseline
Owner: Orket Core

## 1. Objective

Define truthful, durable, and operator-safe lifecycle requirements for Docker sandboxes so completed, failed, lost, reclaimable, or orphaned projects are handled automatically by policy without relying on manual operator inspection.

## 2. Problem Statement

Current sandbox lifecycle behavior can leave Docker resources behind after test or runtime flows. Registry tracking is in-memory, so process restarts can lose ownership knowledge and create orphaned containers, networks, and volumes.

This creates five risks:
1. operator uncertainty about whether a sandbox is still doing work
2. resource leakage across containers, ports, networks, volumes, and images
3. false confidence in cleanup because runtime state and Docker state can drift
4. split ownership after restart or lease expiry
5. terminal evidence that briefly exists but is lost during cleanup

## 3. Terms

1. Sandbox project: a Docker Compose project with prefix `orket-sandbox-`.
2. Durable lifecycle record: persisted lifecycle authority for a sandbox. This is the source of truth for ownership, lifecycle position, cleanup policy, and terminal metadata.
3. State: lifecycle position of a sandbox.
4. Cleanup state: cleanup progression of a sandbox after it becomes cleanup-eligible.
5. Terminal reason: canonical reason code explaining why a sandbox reached a terminal, reclaimable, orphaned, or cleaned condition.
6. Orphan sandbox: Docker sandbox resources with no corresponding durable lifecycle record.
7. Reclaimable sandbox: a sandbox with a durable lifecycle record whose lease has expired and is no longer considered active work.
8. TTL: policy window after which an eligible sandbox must be cleaned automatically.
9. Required terminal evidence: the report/artifact/output required by the workflow contract to prove terminal completion or terminal failure with report.

## 4. Scope

In scope:
1. sandbox lifecycle state model and terminal contract
2. durable sandbox ownership and heartbeat/lease semantics
3. automated cleanup policy and execution
4. startup and periodic reconciliation between durable lifecycle state and Docker state
5. operator visibility for cleanup eligibility, terminal causes, and cleanup outcomes
6. live verification that cleanup removed sandbox-scoped Docker resources

Out of scope:
1. replacing all orchestration with a new queueing platform
2. generic non-sandbox Docker cleanup for unrelated projects
3. UI redesign beyond required lifecycle/cleanup visibility fields

## 5. Lifecycle Model

### 5.1 State

Allowed `state` values:
1. `creating`
2. `starting`
3. `active`
4. `terminal`
5. `reclaimable`
6. `orphaned`
7. `cleaned`

### 5.2 Cleanup State

Allowed `cleanup_state` values:
1. `none`
2. `scheduled`
3. `in_progress`
4. `completed`
5. `failed`

### 5.3 Terminal Reason Authority

`terminal_reason` must be a canonical code.

This section is the canonical reason-code registry for this lane unless and until it is intentionally moved to `docs/specs/` in the same change as runtime adoption.

Minimum required reason codes:
1. `success`
2. `failed`
3. `blocked`
4. `canceled`
5. `create_failed`
6. `start_failed`
7. `restart_loop`
8. `lease_expired`
9. `lost_runtime`
10. `orphan_detected`
11. `orphan_unverified_ownership`
12. `hard_max_age`
13. `cleaned_externally`

Implementations must not substitute free-form text in place of canonical `terminal_reason` codes.

### 5.4 Lifecycle Transition Contract

Allowed transitions:

| From | Event | To | Required reason or notes |
|---|---|---|---|
| `creating` | create accepted | `starting` | none |
| `creating` | create failure | `terminal` | `create_failed` |
| `starting` | health verified | `active` | none |
| `starting` | startup failure | `terminal` | `start_failed` |
| `starting` | lease expired | `reclaimable` | `lease_expired` |
| `active` | workflow terminal outcome | `terminal` | `success`/`failed`/`blocked`/`canceled`/`restart_loop` |
| `active` | lease expired | `reclaimable` | `lease_expired` |
| `active` | hard max age reached | `terminal` | `hard_max_age` |
| `reclaimable` | ownership reacquired | `active` | new `lease_epoch` required |
| `reclaimable` | reclaim TTL elapsed | `terminal` | `lease_expired` |
| `terminal` | cleanup scheduled | `terminal` | `cleanup_state=scheduled` |
| `terminal` | cleanup starts | `terminal` | `cleanup_state=in_progress` |
| `terminal` | cleanup verified complete | `cleaned` | `cleanup_state=completed` |
| `orphaned` | cleanup verified complete | `cleaned` | `cleanup_state=completed` |

Illegal transitions must be rejected and logged as lifecycle contract violations.

No transition may skip directly to `cleaned` without live cleanup verification.

## 6. Initial Policy Defaults

These defaults are required so implementation is unambiguous. Values may be tuned later but must remain explicit.

1. `lease_duration_seconds = 300`
2. `heartbeat_interval_seconds = 30`
3. `ttl_success_minutes = 15`
4. `ttl_failed_hours = 24`
5. `ttl_blocked_hours = 24`
6. `ttl_canceled_hours = 2`
7. `ttl_reclaimable_hours = 2`
8. `ttl_orphan_verified_hours = 1`
9. `ttl_hard_max_age_hours = 72`
10. `restart_threshold_count = 5`
11. `restart_window_seconds = 300`
12. `unhealthy_duration_seconds = 600`

`orphan_unverified_ownership` defaults to quarantine+alert and is not auto-deleted unless an explicit operator override policy is enabled.

## 7. Functional Requirements

### R1. Durable Lifecycle Source of Truth

1. Sandbox lifecycle state must be persisted durably (not in-memory only).
2. Each sandbox record must include:
   - `sandbox_id`
   - `compose_project`
   - `workspace_path`
   - `run_id` and/or `session_id`
   - `owner_instance_id`
   - `lease_epoch`
   - `lease_expires_at`
   - `state`
   - `cleanup_state`
   - `record_version`
   - `created_at`, `last_heartbeat_at`, `terminal_at`
   - `terminal_reason`
   - `cleanup_due_at`
   - `cleanup_attempts`
   - `cleanup_last_error`
   - `required_evidence_ref`
   - `managed_resource_inventory` (containers, networks, and managed volumes expected for verification)
3. The durable lifecycle record is the authoritative runtime record for lifecycle position, ownership, cleanup scheduling, and terminal metadata.
4. Runtime narration, API results, and operator views must not claim lifecycle state that is absent from durable lifecycle state.

### R2. Record Creation Ordering

1. Durable lifecycle record must be written before, or atomically with, sandbox creation intent.
2. Docker sandbox resources must not be created without a corresponding durable lifecycle record.
3. The normal create path must not allow sandbox Docker resources to exist without lifecycle authority.

### R3. Explicit Terminal Contract

A sandbox may transition to `state=terminal` only when one of these contracts is satisfied:
1. completion contract:
   - deploy reached verified running state (or explicit allowed degraded state),
   - automation flow reached terminal outcome,
   - required terminal evidence exists,
   - required terminal evidence is exported to durable storage outside sandbox-managed containers/networks/volumes.
2. pre-active failure contract:
   - create or startup failure occurred before `active`,
   - `terminal_reason` is `create_failed` or `start_failed`,
   - diagnostic evidence reference is recorded when available.

No status message, API response, or operator surface may claim completion before required terminal conditions are satisfied.

`terminal_reason` and `terminal_at` are required whenever `state=terminal`.

### R4. Policy-Driven Cleanup Eligibility

Cleanup eligibility must be deterministic and policy-driven:
1. success path: cleanup after short evidence grace window
2. failed/blocked path: cleanup after diagnostics grace window
3. canceled path: cleanup after cancellation grace window
4. restart-loop path: classify `terminal_reason=restart_loop` when policy thresholds are exceeded, then apply failed-path TTL unless policy states otherwise
5. lease-expired path: if no owner heartbeat before `lease_expires_at`, transition to `reclaimable` with `terminal_reason=lease_expired`
6. reclaim path: after reclaim grace window, transition reclaimable sandbox to terminal cleanup scheduling
5. hard-max-age backstop: cleanup when absolute age exceeds maximum TTL, regardless of intermediate state
7. `cleanup_due_at` must be computed when cleanup eligibility starts
8. `cleanup_state` must move from `none` to `scheduled` when cleanup is first scheduled

### R5. Lease and Heartbeat Semantics

1. Ownership is lease-based and must not be inferred only from recent process activity.
2. Only the current owner for the current `lease_epoch` may extend lease or write heartbeats.
3. Ownership transfer must increment `lease_epoch`.
4. Stale owners must be rejected and must not mutate lifecycle state.
5. Lease expiration must be determined from `lease_expires_at`, not inferred only from heartbeat age.

### R6. Restart-Loop and Unhealthy Classification Policy

Restart-loop classification must be policy-defined.

At minimum policy must define:
1. restart threshold `N`
2. rolling restart window `W`
3. continuous unhealthy threshold `T`

A sandbox must be classified terminal with `terminal_reason=restart_loop` when any required service:
1. restarts more than `N` times inside window `W`, or
2. remains continuously unhealthy beyond threshold `T`.

Restart classification must record structured diagnostic summaries:
1. restart summary
2. health summary
3. terminal reason code

### R7. Reconciliation and Orphan Handling

1. Startup reconciliation must compare durable lifecycle state with real Docker state.
2. Periodic sweeper must repeat reconciliation on configured interval.
3. Unknown Docker sandbox projects matching `orket-sandbox-*` with no durable record must be classified `state=orphaned`.
4. Reconciliation must classify orphans by ownership confidence:
   - verified orphan: positive ownership markers exist (labels and/or record linkage),
   - unverified orphan: prefix-only discovery with no positive ownership markers.
5. Verified orphans are cleanup-eligible by orphan TTL.
6. Unverified orphans default to quarantine+alert and are not auto-deleted unless explicit override policy is enabled.
7. Reconciliation classification must follow deterministic precedence:

| Durable record | Docker state | Classification |
|---|---|---|
| `state=active` | present | active |
| `state=active` | missing | terminal `lost_runtime`, cleanup-eligible by policy |
| `state=terminal` | present | terminal-awaiting-cleanup |
| `state=terminal` and cleanup due passed | present | cleanup-overdue |
| `state=terminal` | missing | terminal `cleaned_externally` or cleaned classification |
| missing record | present + verified ownership | orphaned (`orphan_detected`) |
| missing record | present + unverified ownership | orphaned (`orphan_unverified_ownership`) |
| `state=active` with expired lease | present | reclaimable (`lease_expired`) |

8. Reconciliation must not rely solely on timestamps when direct Docker presence can be verified.
9. Durable-vs-Docker conflicts must be explicit and durably recorded.

### R8. Cleanup Authority and Execution

1. Cleanup operation must be idempotent and safe to retry.
2. Primary cleanup command must be compose down with volume/orphan cleanup for the sandbox project.
3. Discovery may use `orket-sandbox-*` naming, but project prefix alone is insufficient authority for destructive cleanup.
4. Destructive cleanup requires positive Orket ownership authority via one or both:
   - durable lifecycle record match, or
   - Orket-managed Docker labels.
5. Required labels for Orket-managed resources:
   - `orket.managed=true`
   - `orket.sandbox_id=<sandbox_id>`
   - `orket.run_id=<run_id>`
6. Required label coverage:
   - containers: required
   - networks: required
   - managed volumes: required
7. If compose config path is unavailable, fallback cleanup may remove only resources still satisfying positive ownership authority.
8. Cleanup must never target non-sandbox projects or unrelated unlabeled resources.

### R9. Cleanup Verification

1. `state=cleaned` may be recorded only after live Docker verification confirms that sandbox-scoped containers, networks, and managed volumes are absent.
2. `cleanup_state=completed` must not be recorded from command exit status alone.
3. Partial cleanup is failure/incomplete cleanup, not cleaned success.
4. Cleanup attempts and outcomes must be recorded durably.
5. Cleanup verification must compare Docker state against `managed_resource_inventory`.

### R10. Operator Visibility

1. Sandbox listing or equivalent operator view must expose:
   - `sandbox_id`
   - `compose_project`
   - `state`
   - `cleanup_state`
   - `terminal_reason`
   - owner identity
   - heartbeat age or lease expiry
   - restart summary
   - cleanup eligibility
   - cleanup due timestamp
2. Cleanup decisions must emit structured events with:
   - reason code
   - policy match
   - dry-run vs execute mode
   - cleanup result
3. Operator/API surfaces must clearly distinguish:
   - active work
   - terminal awaiting cleanup
   - reclaimable
   - orphaned
   - cleaned
4. Operator/API visibility must reflect durable lifecycle truth, not transient in-memory state.

### R11. Test Behavior Requirements

1. Tests must default to sandbox disabled unless sandbox behavior is under test.
2. Tests that intentionally create sandboxes must register teardown/finalizer cleanup.
3. CI and local acceptance runs must include leak-proof evidence:
   - command proof (for example `docker compose ls -a --format json`),
   - assertion that no unmanaged `orket-sandbox-*` projects remain unless explicitly retained with recorded reason.
4. Integration tests that claim cleanup correctness must use live Docker verification.
5. Structural-only tests are insufficient cleanup proof.

### R12. Concurrency and Fencing

1. Lifecycle mutations must use compare-and-set semantics on `(sandbox_id, lease_epoch, record_version)`.
2. Stale-owner writes must fail closed and be logged.
3. Sweeper must claim cleanup ownership via atomic transition `cleanup_state=scheduled -> in_progress`.
4. Only the active cleanup owner may complete/abort that cleanup attempt.
5. Concurrent cleanup attempts for the same sandbox must be prevented by durable fencing.

## 8. Required Invariants

1. `state` represents lifecycle position only.
2. `cleanup_state` represents cleanup progression only.
3. `terminal_reason` is required when state is `terminal`, `reclaimable`, `orphaned`, or `cleaned` due to external/policy cause.
4. Required terminal evidence must survive sandbox cleanup.
5. Runtime narration must not outrun durable lifecycle truth.
6. Lease validity must be determined by fenced ownership, not best-effort heartbeat inference.
7. Cleanup success must be proven by live Docker verification for integration paths.
8. Docker sandbox resources must not exist without durable lifecycle authority or explicit orphan classification.

## 9. Non-Functional Requirements

1. Truthful behavior: no completion, terminal, or cleanup-success claims without verified state effect.
2. Truthful verification: cleanup correctness must be proven with live Docker checks for integration paths.
3. Resource efficiency: no indefinite restart loops or abandoned sandboxes without terminal/reclaimable/orphaned classification.
4. Durability: ownership, terminal metadata, and cleanup scheduling must survive process restart.
5. Determinism: reconciliation and cleanup eligibility must resolve from durable state, Docker state, and configured policy without ambiguity.
6. Operator safety: destructive cleanup requires positive ownership authority.

## 10. Queue vs Scheduler Decision

1. A queue can manage long-running work dispatch and ownership handoff.
2. A scheduler/sweeper is still required for TTL enforcement, orphan detection, reconciliation, and cleanup execution.
3. Required minimum for this lane: durable lifecycle record plus periodic sweeper, with queue integration optional.

## 11. Acceptance Criteria

1. Creating a sandbox writes a durable lifecycle record before, or atomically with, Docker creation intent.
2. Created sandbox Docker resources carry Orket ownership markers.
3. Terminal workflow completion updates durable `state`, `terminal_reason`, and `cleanup_due_at`.
4. Required terminal evidence is exported to durable non-sandbox storage before completion claims.
5. Startup reconciliation classifies durable-vs-Docker mismatches according to required precedence rules.
6. Unknown `orket-sandbox-*` projects with no durable record are classified as orphaned with verified vs unverified ownership distinction.
7. Sweeper dry-run and execute modes produce deterministic cleanup decisions with reason codes.
8. Lease expiry and ownership transfer prevent stale owners from mutating lifecycle state.
9. Restart-loop classification follows configured policy thresholds and emits diagnostic summaries.
10. End-to-end proof demonstrates:
    - sandbox created
    - durable record present
    - workflow terminal event recorded
    - required evidence exported durably
    - cleanup executed automatically by policy
    - live Docker verification confirms sandbox containers/networks/managed volumes are absent
11. API/operator surfaces expose lifecycle fields consistent with durable source of truth.

## 12. Open Decisions

1. Final tuned TTL values for success, failed, canceled, reclaimable, orphan, and hard-max-age windows.
2. Whether restart thresholds should be globally uniform or tech-stack specific.
3. Whether failed sandboxes should be retained by default in local developer mode with explicit opt-out cleanup policy.
4. Final persistent storage location/backend for required terminal evidence.
5. Whether unverified orphan auto-delete override should exist outside explicit manual approval workflows.
