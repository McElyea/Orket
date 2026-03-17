# Truthful Runtime Conformance Governance Contract

Last updated: 2026-03-17
Status: Active
Owner: Orket Core
Phase closeout authority: `docs/projects/archive/truthful-runtime/TRH03172026-PHASE-E-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/ORKET_OPERATING_PRINCIPLES.md`
2. `docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md`

## Purpose

Define the durable Phase E contract for truthful-runtime conformance, promotion evidence, operator sign-off inputs, and closeout-time drift control.

## Scope

This contract currently covers:
1. behavioral contract suite authority for runtime truth and promotion governance
2. false-green hunt cadence and closeout checklist expectations
3. golden transcript diff policy for canonical truthful-runtime behavior baselines
4. operator sign-off bundle shape for evidence-gated promotion decisions
5. repo introspection report shape using runtime-emitted workspace and capability artifacts
6. cross-spec consistency checker requirements for runtime and docs authority

Out of scope:
1. Phase D memory write and trust semantics, which remain governed by `docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md`
2. new provider/model feature work unrelated to truthful-runtime conformance governance
3. avatar/lipsync truth surfaces that remain outside this bounded closeout

## Behavioral Contract Suite

Required behavioral authority:
1. structural suite: `tests/runtime/test_run_start_artifacts.py`
2. structural suite: `tests/scripts/test_run_runtime_truth_acceptance_gate.py`
3. live suite: `tests/live/test_truthful_runtime_phase_e_completion_live.py`

Blocking user-visible claims:
1. `saved`
2. `synced`
3. `used memory`
4. `searched`
5. `verified`

These claims must remain governed by the truthful-runtime acceptance gate and trust-language review policy before promotion evidence is treated as eligible.

## False-Green Hunt Process

Standing cadence:
1. recurring maintenance through `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`

Required closeout checklist items:
1. runtime claims must follow verified state effect
2. mock-only proof must not be presented as live proof
3. stale phase authority must be removed in the same change as phase closeout

## Golden Transcript Diff Policy

Canonical baseline library:
1. runtime artifact: `canonical_examples_library`

Canonical baseline artifact types:
1. `route_decision_artifact`
2. `repair_ledger`
3. `degradation_labeling`
4. `operator_override_log`

Diff policy:
1. mode: `controlled`
2. block on `missing_canonical_example`
3. block on `unexpected_artifact_type`
4. block on `unreviewed_behavioral_delta`

## Operator Sign-Off Bundle Contract

Required bundle sections:
1. `gate_summary`
2. `release_confidence_scorecard`
3. `promotion_rollback_criteria`
4. `artifact_inventory`
5. `decision_record`

Required decision fields:
1. `promotion_recommendation`
2. `required_operator_action`

If the evidence package reports `promotion_recommendation = eligible`, then `required_operator_action` must be `operator_signoff_required`.

## Repo Introspection Report Contract

Source artifacts:
1. `workspace_state_snapshot`
2. `capability_manifest`

Required report fields:
1. `workspace_path`
2. `workspace_type`
3. `workspace_hash`
4. `file_count`
5. `capabilities_allowed`
6. `capabilities_used`
7. `run_determinism_class`

Emission path:
1. `observability/<run_id>/runtime_contracts/`

## Cross-Spec Consistency Checker

Required checks:
1. `runtime_truth_contract_drift_report`
2. `python scripts/governance/check_docs_project_hygiene.py`

Failure policy:
1. `block_closeout`

## Live Evidence Authority

1. Live suite: `tests/live/test_truthful_runtime_phase_e_completion_live.py`
2. Contract coverage:
   `tests/runtime/test_conformance_governance_contract.py`,
   `tests/runtime/test_run_start_artifacts.py`,
   `tests/runtime/test_runtime_truth_drift_checker.py`,
   `tests/runtime/test_runtime_truth_trace_ids.py`
3. Governance coverage:
   `tests/scripts/test_check_conformance_governance_contract.py`,
   `tests/scripts/test_run_runtime_truth_acceptance_gate.py`,
   `tests/scripts/test_generate_runtime_truth_evidence_package.py`
