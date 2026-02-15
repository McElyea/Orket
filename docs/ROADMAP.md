# Orket Roadmap

Last updated: 2026-02-15.

## Operating Constraints (Current)
1. Orket engine loop remains the runtime; storage backend is pluggable.
2. Monolith remains default; microservices stay policy-controlled.
3. Frontend policy is Vue-only when a frontend is required.
4. iDesign is backburnered and not an active gate.
5. Small-task minimum team is one builder (`coder` or `architect`) plus one mandatory `code_reviewer`.
6. Replan limit is terminal: `replan_count > 3` halts with rejection semantics.

## Priority 1: Gitea-Backed State Adapter (Top Priority)
Objective: add a remote state store + work queue surface via Gitea without changing the Orket runtime loop.

### P1-A. GiteaStateAdapter v1 (Single-Runner Safe)
1. Implement `GiteaStateAdapter` for issues labeled `status/ready`.
2. Implement optimistic concurrency for updates (ETag/version compare-and-swap).
3. Implement lease contract in issue snapshot:
   - `lease.owner_id`
   - `lease.acquired_at`
   - `lease.expires_at`
   - `lease.epoch`
4. Tolerate duplicate pickup attempts with idempotent acquire/write behavior.
5. Acceptance criteria:
   - Two acquire attempts on the same issue do not produce dual ownership.
   - Stale writer is rejected by CAS.
   - Repeated transition/event writes are idempotent.
   - Duplicate delivery of the same acquire/write request is a no-op after first success.

### P1-B. State Model in Gitea
1. Issue body stores compact snapshot only:
   - card identity/metadata
   - current state
   - lease block
   - minimal execution fields
2. Issue comments are append-only event log:
   - guard failures
   - retries
   - fix hints
   - transitions
   - errors
3. Acceptance criteria:
   - Snapshot remains compact and parseable.
   - Full timeline is reconstructable from comments + snapshot head.

### P1-C. Concurrency + Transition Safety
1. Add explicit state transition preconditions (allowed `from -> to` map).
2. Apply CAS + transition validation in every state mutation.
3. Add lease expiration + takeover rules keyed by `lease.epoch`.
4. Acceptance criteria:
   - Invalid transitions fail deterministically.
   - Expired leases can be reclaimed without split-brain updates.
   - Allowed `from -> to` transitions are sourced from the existing Orket state machine contract.

### P1-D. Failure Semantics + Resilience
1. Classify and handle adapter failure classes:
   - rate limit
   - stale ETag/version conflict
   - network partition/timeout
   - auth/permission errors
2. Add retry with bounded backoff for transient adapter failures.
3. Mark non-retryable adapter failures as terminal for the affected card transition.
4. Acceptance criteria:
   - Transient failures recover without corrupting card state.
   - Non-retryable failures surface clear terminal reasons.
   - Adapter emits structured logs for all failure classes including `backend`, `card_id`, and `operation`.

### P1-E. Rollout Strategy
1. Phase 1: single-runner pilot on `gitea` backend.
2. Phase 2: hardening pass with contention/failure injection tests.
3. Phase 3: multi-runner support (after Phase 2 pass criteria).
4. Acceptance criteria:
   - `local` remains default and stable.
   - `gitea` remains explicitly marked experimental until contention suite is green.
   - No features depend exclusively on gitea backend semantics until Phase 3 is complete.

## Priority 2: Determinism Maintenance (Recurring)
Objective: keep current quality gates green while Priority 1 lands.

1. Keep these commands green:
   - `python -m pytest tests -q`
   - `python scripts/check_dependency_direction.py`
   - `python scripts/check_volatility_boundaries.py`
2. Keep readiness artifacts fresh:
   - `python scripts/run_monolith_variant_matrix.py --execute --out benchmarks/results/monolith_variant_matrix.json`
   - `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
   - `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`

## Priority 3: Architecture Pilot Monitoring (Recurring)
Objective: continue side-by-side monolith vs microservices evidence while runtime/storage work advances.

1. Refresh pilot matrix:
   - `python scripts/run_architecture_pilot_matrix.py --execute --out benchmarks/results/architecture_pilot_matrix.json --rotate-prev-out benchmarks/results/architecture_pilot_matrix_prev.json`
2. Re-evaluate stability:
   - `python scripts/check_microservices_pilot_stability.py --artifacts benchmarks/results/architecture_pilot_matrix_prev.json benchmarks/results/architecture_pilot_matrix.json --required-consecutive 2 --out benchmarks/results/microservices_pilot_stability_check.json`
3. Keep runtime policy output aligned:
   - `microservices_unlocked`
   - `microservices_pilot_stable`

## Backburner (Not Active)
1. Additional frontend frameworks beyond Vue.
2. iDesign-first enforcement.
3. Architecture expansion beyond controlled microservices policy/pilot monitoring.
