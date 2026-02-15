# Orket Roadmap

Last updated: 2026-02-14.

## Operating Constraints (Current)
1. Execution priority is Local-First Orket packaging (Phase 1).
2. Monolith remains the default architecture; microservices are unlocked for controlled pilots behind explicit enablement.
3. Frontend policy is Vue-only when a frontend is required.
4. iDesign is backburnered and not a gating requirement for current roadmap execution.
5. Small-task minimum team is one builder (`coder` or `architect` variant) plus one mandatory `code_reviewer` (never self-review).
6. Replan limit is terminal: `replan_count > 3` halts with terminal failure/rejection semantics.

## Priority A: Local-First Orket Packaging (Phase 1)
Objective: ship a deterministic, local-first deployable Orket format and runtime entrypoints using the existing engine/state machine.

### A1. `orket.yaml` Manifest Contract v1
1. Define a schema-backed manifest contract with required sections:
   - `metadata` (name, version, engine compatibility)
   - `model` (preferred/minimum/fallback/override policy)
   - `agents`
   - `guards`
   - `stateMachine`
   - `persistence`
   - `permissions`
2. Add canonical fixtures: one valid manifest and multiple invalid manifests.
3. Acceptance criteria:
   - Missing required sections fail validation.
   - Unknown/invalid enum values fail validation.
   - Engine compatibility field is mandatory and parseable.

### A2. `orket validate` CLI
1. Implement `orket validate` for manifest + bundle directory checks.
2. Validate cross-file references (state machine file, prompts/agents/guards references).
3. Validate permission block shape (filesystem/network/tools).
4. Acceptance criteria:
   - Valid fixture passes with exit code `0`.
   - Invalid fixtures fail with deterministic error codes/messages.

### A3. `orket pack` and `orket inspect` CLI
1. Implement `orket pack` to build a `.orket` archive from a source directory.
2. Implement `orket inspect` to print metadata, compatibility, and permission summary.
3. Acceptance criteria:
   - `pack` output contains manifest plus expected assets.
   - `inspect` works both from directory and `.orket` archive.
   - Invalid bundle returns non-zero with clear reason.

### A4. Deterministic Bundle Layout
1. Standardize canonical archive layout:
   - `orket.yaml`
   - `state_machine.json`
   - `prompts/`
   - `agents/`
   - `guards/`
   - optional `models/`
   - optional `assets/`
2. Enforce deterministic packaging behavior:
   - stable file ordering
   - normalized paths
   - no path traversal entries
3. Acceptance criteria:
   - Packing same source twice yields identical archive hash.
   - Unsafe paths are rejected.

### A5. Compatibility and Model Negotiation Checks
1. Enforce `engineVersion` compatibility at validate/run time.
2. Enforce model policy:
   - `preferred`
   - `minimum`
   - ordered `fallback`
   - `allowOverride`
3. Acceptance criteria:
   - Incompatible engine range fails fast.
   - Missing model candidates produce deterministic failure.
   - Override behavior matches manifest policy.

## Not In Scope For Phase 1
1. Registry/publish/pull workflow.
2. Bundle signatures/trust chain.
3. Bundled large model weights distribution.
4. Desktop app wrapper UX.

## Priority B: Microservices Unlock
Objective: continue architecture expansion only after Priority A is shipped and stable.

### B1. Unlock Criteria
1. Run unlock evidence pipeline and enforce unlock criteria:
   - `python scripts/run_microservices_unlock_evidence.py --require-unlocked`
2. Record pilot decision artifact from unlock output:
   - `python scripts/decide_microservices_pilot.py --unlock-report benchmarks/results/microservices_unlock_check.json --out benchmarks/results/microservices_pilot_decision.json`
3. If unlock passes, enable microservices explicitly via `ORKET_ENABLE_MICROSERVICES=true` for controlled pilots.
4. Keep monolith as default until pilot metrics are stable.

### B1. Latest Decision (2026-02-14)
1. `microservices_pilot_decision.json` result: `enable_microservices=true`.
2. Active recommendation is now `ORKET_ENABLE_MICROSERVICES=true` for controlled pilots.
3. Unlock criteria currently pass with `pass_rate=0.875`, `runtime_failure_rate=0.0`, `reviewer_rejection_rate=0.0`.
4. Governance stability criteria currently pass (`terminal_failure_rate=0.0`, `guard_retry_rate=0.0`, `done_chain_mismatch=0`).

## Backburner (Not Active)
1. iDesign-first enforcement or iDesign-specific mandatory flows.
2. Additional frontend frameworks beyond Vue.
3. Broad architecture expansion beyond controlled microservices pilots.

## Execution Plan (Remaining)
1. Start controlled microservices pilot runs with explicit enablement:
   - set `ORKET_ENABLE_MICROSERVICES=true` for pilot sessions only.
2. Add pilot evidence slices comparing monolith vs microservices on the same project set.
3. Keep monolith default until pilot metrics match/exceed monolith stability for two consecutive batches.

## Weekly Proof (Required)
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python scripts/run_monolith_variant_matrix.py --execute --out benchmarks/results/monolith_variant_matrix.json`
5. `python scripts/check_monolith_readiness_gate.py --matrix benchmarks/results/monolith_variant_matrix.json --policy model/core/contracts/monolith_readiness_policy.json --allow-plan-only`
6. `python scripts/check_microservices_unlock.py --matrix benchmarks/results/monolith_variant_matrix.json --readiness-policy model/core/contracts/monolith_readiness_policy.json --unlock-policy model/core/contracts/microservices_unlock_policy.json --live-report benchmarks/results/live_acceptance_patterns.json --out benchmarks/results/microservices_unlock_check.json`
7. `python scripts/decide_microservices_pilot.py --unlock-report benchmarks/results/microservices_unlock_check.json --out benchmarks/results/microservices_pilot_decision.json`
8. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
9. `python -m scripts.report_live_acceptance_patterns --matrix benchmarks/results/monolith_variant_matrix.json`
