# Orket Roadmap (Active Only)

Last updated: 2026-02-14.

## North Star
Ship one canonical, reliable pipeline that passes this exact flow with deterministic guard governance:
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard`

If this flow is not mechanically proven with canonical assets and machine-readable guard contracts, we are not done.

## Operating Rules
1. Keep changes small and reversible.
2. No architecture pivots while stabilization work is active.
3. Every change must map to a failing or missing test.
4. Single owner per rule:
   - `Role + Skill + Dialect` define behavior, style, structure, and intent.
   - `Guards` enforce runtime correctness constraints.
   - `Guard Agent` validates only and never generates content.
5. Guard outcomes must be deterministic, machine-readable, and diagnosable from runtime artifacts.

## Priority Order (Highest First)
1. `P0`: Guard system scalability and loop hardening.
2. `P1`: Prompt engine coherence and promotion governance.
3. `P2`: Observability and model compliance scoring.
4. `P3`: Architecture boundary enforcement and maintenance checks.

## P0: Guard System Scalability and Loop Hardening
Objective: prevent guard bloat, scope drift, and retry spirals while keeping guard outcomes deterministic.

### P0-R1 Guard Rule Registry
1. Add canonical `GuardRuleRegistry` entries with `rule_id`, owner domain, severity, and verification scope.
2. Enforce unique `rule_id` and single-owner constraints in CI and runtime validation.
3. Reject overlapping or contradictory rules at load time.

Exit Criteria:
1. Registry is the single source of truth for hallucination/security/consistency rules.
2. Contract and guard loading fail fast on duplicate or conflicting rule ownership.

### P0-R2 Canonical Verification Scope Builder
1. Implement one scope builder for all guard checks:
   - `workspace`
   - `provided_context`
   - `declared_interfaces`
2. Route all guard validations through this canonical scope object.
3. Add regression tests for false-positive and false-negative reference checks.

Exit Criteria:
1. No guard performs ad hoc scope resolution.
2. Reference checks are deterministic across runs.

### P0-R3 Retry Fingerprint Cutoff
1. Introduce retry fingerprinting from sorted violation codes + normalized output hash.
2. Detect repeated failures and force `terminal_failure` with `MODEL_NON_COMPLIANT`.
3. Apply fingerprint checks before retry counter increments.

Exit Criteria:
1. Repeated identical failures terminate deterministically without extra retry churn.
2. Live acceptance reports expose fingerprint-triggered terminal failures.

### P0-R4 Guard Evaluator and Controller Split
1. Split guard execution into:
   - `GuardEvaluator`: evaluate checks and emit `GuardContract`.
   - `GuardController`: apply retry/escalation policy from contract + loop control.
2. Keep policy decisions out of check implementations.
3. Add unit and integration tests for pass/retry/terminal transitions.

Exit Criteria:
1. Guard checks and loop policy are isolated and testable independently.
2. Retry policy changes do not require touching guard rule code.

### P0-R5 Hallucination Scope Partitioning
1. Partition context into `active_context`, `passive_context`, and `archived_context` for hallucination checks.
2. Restrict strict hallucination validation to active scope while preserving traceability.
3. Add coverage for legitimate references that should not false-fail.

Exit Criteria:
1. Hallucination guard false positives are reduced without weakening strict checks.
2. Evidence and location data remain machine-readable in violations.

## P1: Prompt Engine Coherence and Promotion Governance
Objective: prevent prompt drift and governance stalls as role/skill/dialect assets evolve.

### P1-R1 Prompt Linter
1. Implement lint rules for schema compliance, placeholder consistency, dialect compatibility, guard injection points, and required metadata.
2. Emit lint violations in canonical guard-like format (`rule_id`, severity, location, evidence).
3. Gate CI and promotion paths on strict lint failures.

Exit Criteria:
1. Prompt assets fail fast on structural drift.
2. Lint output is deterministic and auditable.

### P1-R2 Promotion Criteria Enforcement
1. Encode promotion policy (guard pass rate, strict-violation limits, terminal-failure limits, regression checks, approval signal).
2. Block candidate promotion when criteria are not met.
3. Surface promotion blockers in machine-readable reports.

Exit Criteria:
1. Draft/candidate backlog is governed by explicit, enforced promotion rules.
2. Stable promotion cannot bypass policy checks.

## P2: Observability and Model Compliance Scoring
Objective: make guard behavior and model compliance measurable per run, model, prompt, and version.

### P2-R1 Structured Runtime Events
1. Emit structured events with prompt lineage, guard contracts, retry data, terminal reasons, output hash, latency, and token metrics.
2. Persist events in durable artifacts for post-mortem analysis.
3. Keep event schema stable and versioned.

Exit Criteria:
1. Any run can be reconstructed from stored event artifacts.
2. Guard failures and escalation paths are diagnosable without manual log scraping.

### P2-R2 Model Compliance Scoring
1. Compute per-model aggregate metrics:
   - hallucination/security/consistency violation rates
   - average retries
   - terminal failure rate
   - guard pass rate
2. Publish a composite compliance score and trend deltas in acceptance reporting.
3. Use scores to gate default model selection and regression alerts.

Exit Criteria:
1. Model regressions are detected automatically from compliance deltas.
2. Default model decisions are evidence-based and repeatable.

## P3: Architecture Boundaries and Maintenance
Objective: keep dependency direction and volatility boundaries green while higher-priority stabilization work lands.

Recurring Verification:
1. `python scripts/check_dependency_direction.py`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

## Weekly Proof
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`
