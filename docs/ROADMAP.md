# Orket Roadmap (Fresh Start)

Last updated: 2026-02-13.

## North Star
Ship one canonical, reliable agent pipeline that passes this exact flow:
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard` finalizes outcome

If this flow is not mechanically proven, we are not done.

## Operating Rules
1. Simple over clever.
2. No broad refactors while recovery work is in progress.
3. Fix only what blocks the acceptance contract.
4. Every change must be tied to a failing or missing test.

## Primary Recovery Plan

### Phase P0: Lock The Contract
Objective: define one unambiguous acceptance contract.

Work:
1. Freeze canonical role names:
   - `requirements_analyst`, `architect`, `coder`, `code_reviewer`, `integrity_guard`
2. Freeze canonical seat order for the basic test:
   - `REQ-1 -> ARC-1 -> DEV-1 -> REV-1 -> guard finalization`
3. Freeze canonical artifacts required:
   - `agent_output/requirements.txt`
   - `agent_output/design.txt`
   - `agent_output/main.py`
4. Freeze required state path:
   - role work in `in_progress`
   - review handoff in `code_review`
   - guard-only finalization to `done` or `blocked`

Done when:
1. Contract is encoded in test assertions (not comments).
2. Contract is documented in `docs/TESTING_POLICY.md` and `docs/RUNBOOK.md`.

Verification:
1. `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard -q`

### Phase P1: Make Canonical Assets Runnable
Objective: ensure repo-native assets can execute without test-only scaffolding.

Work:
1. Create/update canonical role files in `model/core/roles/` for all roles required by canonical teams.
2. Repair team-role references in `model/core/teams/*.json`.
3. Repair epic-team-seat references in `model/core/epics/*.json`.
4. Add CI integrity gate for asset references:
   - team seat role -> role file must exist
   - epic team -> team file must exist
   - epic seat -> seat must exist in referenced team

Done when:
1. No missing role/team/seat links in `model/core/**`.
2. Loader + runtime can execute canonical epic definitions without `CardNotFound` for roles.

Verification:
1. `python -m pytest tests/platform/test_config_loader.py -q`
2. `python -m pytest tests/platform/test_model_asset_integrity.py -q` (new)

### Phase P2: Acceptance Gate Must Use Canonical Assets
Objective: stop proving success with synthetic fixtures only.

Work:
1. Keep one deterministic fixture test for engine behavior.
2. Add canonical-asset acceptance test that loads repo model assets directly.
3. Ensure the canonical test validates:
   - seat/role order
   - expected artifacts
   - guard terminal decision by `integrity_guard`
4. Rename pipeline test internals from `developer` to `coder` where contract requires it.

Done when:
1. Acceptance lane fails if `coder` step is missing/replaced.
2. Acceptance lane fails if canonical assets are inconsistent.

Verification:
1. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`
2. `python -m pytest tests/integration/test_system_acceptance_flow.py -q`

### Phase P3: Boundary Enforcement That Matches Reality
Objective: enforce volatility boundaries without loopholes.

Work:
1. Extend boundary checks to detect adapter coupling through root facades (not only direct `orket.adapters.*` imports).
2. Reduce legacy bridge usage from runtime orchestration paths (`orket.orket` compatibility hops).
3. Keep `scripts/check_volatility_boundaries.py` as pre-merge gate.

Done when:
1. Application layer cannot depend on adapters indirectly through umbrella modules without explicit allowlist.
2. Boundary script catches intentional violation in a red test.

Verification:
1. `python scripts/check_volatility_boundaries.py`
2. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

### Phase P4: Documentation Reset
Objective: docs become reliable for human/agent execution.

Work:
1. Rewrite stale architecture docs to match current module layout.
2. Update process docs with current module paths and commands.
3. Remove or archive historical docs that conflict with current runtime.

Done when:
1. No critical doc references point to removed or relocated runtime paths.
2. New contributor can run acceptance gate without tribal knowledge.

Verification:
1. `rg -n "orket/services/|orket/infrastructure/|orket/orchestration/orchestrator.py|orket/tool_families/" docs ARCHITECTURE.md`
2. Manual runbook dry-run by following docs only.

## Weekly Execution Cadence
1. Monday: pick one blocking failure from P1/P2.
2. Midweek: ship smallest fix + test.
3. Friday: run full gates and record status.

Required weekly proof:
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python scripts/report_failure_modes.py --out benchmarks/results/failure_modes.json`

## Exit Criteria
All must be true for two consecutive runs:
1. Canonical acceptance pipeline passes with repo-native assets and exact role chain (`requirements_analyst -> architect -> coder -> code_reviewer -> integrity_guard`).
2. No model asset reference integrity failures.
3. Boundary checks pass without manual exceptions.
4. Docs match runtime paths and operational commands.
