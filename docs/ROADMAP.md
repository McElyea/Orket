# Orket Roadmap

Last updated: 2026-02-14.

## Current State
Core stabilization (`P0` through `P4`) is complete.
Phase A, Phase B, and Phase C implementation items are complete.

Locked foundations:
1. Guard contract formalization.
2. Guard rule registry with rule ownership.
3. Verification scope normalization.
4. Retry fingerprint terminal controls.
5. Prompt linter and promotion criteria enforcement.
6. Runtime event envelope and schema counters.
7. Model compliance reporting in acceptance patterns.

Non-negotiable rule:
1. Any change that weakens a locked foundation must include a failing test first and a replacement enforcement path.

## Canonical Pipeline (Locked)
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard`

## Priority Path (Execute In Order)

### Phase A: Prompt and Guard Determinism
Objective: reduce drift, false positives, and non-actionable retries.

1. `A1` Prompt drift control (Complete)
   - Scope: canonical role structure templates and conformance checks.
   - Trigger: prompt-linter drift violations > 3/week across canonical roles.
   - Done when: template regeneration path exists and role conformance tests pass in CI.
   - Completed evidence:
     - `scripts/regenerate_canonical_roles.py` added for deterministic template regeneration.
     - `PL006` canonical role conformance checks added to prompt linter.
     - CI-facing conformance tests added in `tests/platform/test_canonical_role_conformance.py`.
2. `A2` Guard overreach control (Complete)
   - Scope: isolate strict rules with false positives and narrow their scope.
   - Trigger: guard false-positive rate > 5% for 2 weekly proof runs.
   - Done when: false-positive regressions are covered by tests and threshold is back under limit.
   - Progress (Slice 1 complete):
     - Narrowed strict-grounding scan to non-JSON residue only to avoid false positives from tool payload content.
     - Added regression coverage for strict-grounding overreach boundaries in `tests/application/test_turn_executor_middleware.py`.
   - Progress (Slice 2 complete):
     - Added per-`rule_id` guard non-progress counters to live acceptance metrics collection.
     - Added aggregate `guard_rule_violation_counts` to pattern reports for direct strict-rule isolation.
3. `A3` Retry hint specificity (Complete)
   - Scope: tie corrective fix hints to `rule_id` and violation evidence.
   - Trigger: repeated failure fingerprint beyond `max_retries`.
   - Done when: repeated violations reach deterministic terminal paths without retry loops.
   - Completed evidence:
     - Corrective reprompt now emits rule-specific fixes with `rule_id` and evidence.
     - `turn_corrective_reprompt` events now include `rule_fix_hints` for diagnostics.
4. `A4` Context budget control (Complete)
   - Scope: enforce active/passive/archived context budgets.
   - Trigger: retries > 1.0 average and prompt size growth > 25% over baseline.
   - Done when: context budget checks and regression tests prevent bloat regressions.
   - Completed evidence:
     - Verification scope supports configurable budgets:
       `max_workspace_items`, `max_active_context_items`, `max_passive_context_items`, `max_archived_context_items`, `max_total_context_items`.
     - Hallucination scope diagnostics enforce budget violations with explicit rule IDs.
     - Orchestrator now supports `process_rules.verification_scope_limits`.

### Phase B: Model and Dialect Reliability
Objective: keep model portability while reducing parser and compliance failures.

1. `B1` Dialect version contract (Complete)
   - Scope: versioned dialect contract with parser fixtures per model family.
   - Trigger: dialect parse failure rate > 2% in acceptance runs for any model family.
   - Done when: dialect fixtures pass and known-good dialect versions are pinned.
   - Completed evidence:
     - Added pinned contract file: `model/core/contracts/dialect_version_contract.json`.
     - Added platform tests:
       - `tests/platform/test_dialect_version_contract.py`
       - validates pinned version alignment and parser fixtures per dialect family.
2. `B2` Compliance-driven model routing (Complete)
   - Scope: enforce demotion/fallback when model compliance remains poor.
   - Trigger: compliance score < 85 for 3 weekly proof runs.
   - Done when: routing policy demotes non-compliant models automatically with traceable events.
   - Completed evidence:
     - `ModelSelector` now supports `model_compliance_policy` with:
       `min_score`, `fallback_model`, `blocked_models`, `model_scores`, and `score_source`.
     - Automatic demotion/fallback is enforced in selection path.
     - Traceable model demotion decisions are emitted via `model_selection_decision` events.
     - Coverage added in `tests/application/test_model_selector_compliance.py`.

### Phase C: Governance Throughput and Scope Discipline
Objective: prevent governance stalls and ownership overlap.

1. `C1` Promotion flow SLA (Complete)
   - Scope: force candidate prompt resolution (promote/deprecate/renew) within SLA.
   - Trigger: candidate prompts older than 14 days without a decision.
   - Done when: stale candidate prompts are auto-resolved or explicitly renewed.
   - Completed evidence:
     - Added CLI enforcement path: `python -m orket.interfaces.prompts_cli --root . enforce-sla`.
     - Stale candidate prompts now auto-deprecate unless explicitly renewed via `--renew <prompt_id>`.
     - Coverage added in `tests/application/test_prompts_cli.py`.
2. `C2` Role boundary audit (Complete)
   - Scope: detect and resolve overlapping role ownership in runtime rule domains.
   - Trigger: more than 2 roles own the same runtime rule domain.
   - Done when: ownership map is singular per domain and validated by policy checks.
   - Completed evidence:
     - Added explicit ownership contract: `model/core/contracts/role_runtime_domain_ownership.json`.
     - Added CI-facing validation: `tests/platform/test_role_runtime_domain_ownership.py`.
3. `C3` Prompt engine modular boundary checks (Complete)
   - Scope: enforce ordered stages (`resolve -> validate -> select -> render`) with contract tests.
   - Trigger: resolver changes touch more than 3 independent resolution steps.
   - Done when: stage contracts are tested and resolver churn is isolated by module.
   - Completed evidence:
     - Added explicit resolver stage contract metadata (`resolver_stages`) in prompt layers.
     - Added stage-order test coverage in `tests/application/test_prompt_resolver.py`.
4. `C4` Over-formalization brake (Complete)
   - Scope: release-level check that policy churn must produce measurable reliability gains.
   - Trigger: 2 consecutive releases with policy churn but no reliability gain.
   - Done when: release gate blocks additional formalization without impact evidence.
   - Completed evidence:
     - Added release gate script: `scripts/check_policy_release_gate.py`.
     - Gate compares previous/current reliability snapshots and fails on policy churn with no measurable gain.
     - Coverage added in `tests/application/test_policy_release_gate.py`.

## Hybrid Pruning Policy (Required)
Objective: prevent stale projects from bypassing pruning and avoid rule inflation.

### Triggers
1. Time trigger: mandatory quarterly pruning review.
2. Metrics trigger: pruning review when false positives, guard latency, or rule overlap exceeds thresholds.
3. Staleness trigger: if activity is low/none for 60 days, run synthetic replay pruning on canonical fixtures.

### Candidate Gate
A rule is a prune candidate when at least one is true:
1. No unique violations for 90 days.
2. Fully subsumed by another strict `rule_id`.
3. Produces repeated false positives above threshold.

### Safe Removal Flow
1. Mark rule as `deprecated`.
2. Run full weekly proof plus synthetic replay.
3. Remove in next release window only if regression-free.
4. Keep rollback map for one release.

### Anti-Edge-Case Safeguard
1. Quarterly review plus synthetic replay is mandatory even for near-zero traffic projects.

## Long-Term Watchlist
1. Contributor drift in prompt/guard style.
2. Ecosystem fork compatibility divergence.
3. Over-reliance on one model family.
4. Guard rule inflation.
5. Orchestrator complexity creep.

## Weekly Proof (Recurring)
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`

## Completed Baseline Work
1. `P0`: Guard contract formalization and deterministic loop controls.
2. `P1`: Prompt linting and promotion governance.
3. `P2`: Runtime event envelope and model compliance reporting.
4. `P3`: Architecture boundary enforcement and maintenance checks.
5. `P4`: Operational hardening of proof cadence and reporting stability.
