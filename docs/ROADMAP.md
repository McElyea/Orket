# Orket Roadmap (Fresh Start)

Last updated: 2026-02-14.

## North Star
Ship one canonical, reliable agent pipeline that passes this exact flow:
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard` finalizes outcome

If this flow is not mechanically proven, we are not done.

## Current Status Snapshot
1. `O1 Guardrail Control Plane`: In progress.
2. `P0 Data-Driven Behavior Recovery Loop`: Active.
3. `P1 Canonical Assets Runnable`: In progress.
4. `P2 Acceptance Gate Uses Canonical Assets`: In progress.
5. `P3 Boundary Enforcement`: Mostly complete, keep as guardrail.
6. `P4 Documentation Reset`: In progress.

## Operating Rules
1. Simple over clever.
2. No broad refactors while recovery work is in progress.
3. Fix only what blocks the acceptance contract.
4. Every change must be tied to a failing or missing test.

## Primary Recovery Plan

### Phase O1: Guardrail Control Plane (Before P0)
Objective: add deterministic control-plane enforcement so P0 tuning runs on a stable governance substrate.
Status: Completed.

Scope:
1. Stage gate policy per seat/stage:
   - `auto`, `review_required`, `approval_required`.
2. Strict guard rejection contract:
   - rejection requires non-empty rationale and remediation actions.
3. Risk-focused rollout:
   - apply hard gating to `integrity_guard` first.
4. Keep behavior mechanical:
   - invalid guard payloads trigger deterministic retry path, not silent pass/fail.

Work:
1. [x] Add stage gate mode policy seam in orchestration loop node.
2. [x] Include stage gate mode in turn execution context for visibility and downstream policy use.
3. [x] Enforce strict guard rejection payload validation (`rationale` + `remediation_actions`) on guard-rejected outcomes.
4. [x] Log invalid payload event with machine-readable reason (`guard_payload_invalid`).
5. [x] Add persistent `pending_gate_requests` ledger for explicit pause/resume gating.
6. [x] Add `approval_required` flow for selected high-impact tools.

Done when:
1. Guard rejection without rationale/remediation can no longer pass as valid output.
2. Stage gate mode is available in runtime context for every turn.
3. Guard payload invalid events are observable and correlate to retry behavior.
4. Tool-level approval-required gates can create pending requests and block execution.

Verification:
1. `python -m pytest tests/application/test_decision_nodes_planner.py -q`
2. `python -m pytest tests/application/test_orchestrator_epic.py -q`
3. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`

### Phase P0: Data-Driven Behavior Recovery Loop
Objective: use run evidence to systematically improve weak model behavior and raise canonical completion rate.
Status: Active.

Why this is now P0:
1. Contract lock is complete enough to enforce behavior mechanically.
2. The blocker is no longer contract definition; it is repeated non-progress and guard over-blocking.
3. We now have stable telemetry from three layers:
   - per-run raw artifacts in `.pytest_live_loop/`
   - run/session summaries in `run_ledger`
   - aggregate trend rows in `workspace/observability/live_acceptance_loop.db`

Inputs this phase will use:
1. Live loop aggregate rows:
   - `live_acceptance_batches`, `live_acceptance_runs`
   - fields: `passed`, `session_status`, `model`, `metrics_json`, `db_summary_json`
2. Run ledger records:
   - `run_ledger.status`, `failure_class`, `failure_reason`, `summary_json`, `artifact_json`
3. Raw turn evidence:
   - `workspace/observability/<run_id>/<issue>/<turn>/checkpoint.json`
   - `workspace/orket.log` events: `turn_corrective_reprompt`, `turn_non_progress`, `dependency_block_propagated`, `guard_rejected`
4. Optional Gitea artifact exports:
   - `artifact_json.gitea_export` links for external review and cross-machine diffing

P0 Workstream A: Prompt Contract Reliability (First-Turn Success)
Goal: reduce deterministic first-turn failures where required tool/status actions are missing.

Work:
1. Build a per-role failure matrix from latest loop batches:
   - count missing required action tools per role.
   - count missing required status transitions per role.
2. Harden role prompts for weak steps in this order:
   - `requirements_analyst` first, then `architect`, then `coder`.
3. Add explicit "must include both actions in same response" framing where model drift is highest.
4. Keep corrective reprompt, but tighten reprompt text to show minimal valid response template.
5. Add targeted tests that prove a malformed single-tool response is corrected on first reprompt for each role.

Done when:
1. `turn_non_progress` rate for `requirements_analyst` drops below 5% over 20 runs on selected baseline models.
2. No deterministic "write_file-only" failure for baseline model set in two consecutive loop batches.

Verification:
1. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b llama3.1:8b --iterations 3`
2. Query latest `live_acceptance_runs.metrics_json` for:
   - `turn_corrective_reprompt`
   - `turn_non_progress`

P0 Workstream B: Guard Decision Quality (False-Block Reduction)
Goal: stop premature guard blocks that propagate dependency failures.

Work:
1. Extract all `guard_rejected` events and correlate with:
   - prior role output completeness
   - absence/presence of explicit guard rationale
2. Enforce minimum guard rejection payload:
   - non-empty rationale
   - at least one actionable remediation item
3. Adjust guard policy so rejection without rationale is invalid and triggers corrective reprompt.
4. Add tests for:
   - rejection without rationale -> invalid
   - valid rejection with rationale -> accepted and propagated

Done when:
1. Guard rejections with empty rationale are eliminated in baseline loop runs.
2. `dependency_block_propagated` caused by rationale-empty guard decisions is zero.

Verification:
1. `python -m pytest tests/application/test_orchestrator_epic.py -q`
2. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 3`

P0 Workstream C: Model Routing and Compatibility Hygiene
Goal: remove avoidable failures from routing/install mismatches and weak-model assignments.

Work:
1. [x] Preflight installed model inventory before loop execution (`ollama list` integration in loop path).
2. [x] Fail fast with clear skip classification for uninstalled model tags.
3. [ ] Maintain a baseline allowlist for canonical flow and a quarantine list for unstable models.
4. [ ] Log model capability outcomes per role to inform routing defaults.

Done when:
1. `ModelConnectionError` from uninstalled tags is zero in scheduled loop batches.
2. Baseline model set and routing policy are documented and enforced.

Verification:
1. `ollama list`
2. `python scripts/run_live_acceptance_loop.py --models <baseline_set> --iterations 2`

P0 Workstream D: Evidence Pipeline Discipline
Goal: keep evidence useful and queryable while retaining raw diagnostics for deep dives.

Work:
1. [x] Keep `.pytest_live_loop/` enabled during recovery period.
2. [x] Keep folder-level ignore rules so diagnostics never pollute git status.
3. [x] Store aggregate/trend facts in `workspace/observability/live_acceptance_loop.db`.
4. [x] Store per-run summary/artifact refs in `run_ledger`.
5. [x] Export raw evidence to Gitea when enabled; treat export as best-effort, non-blocking.
6. [x] Add one SQL helper/report script for latest-batch pattern summaries.

Done when:
1. Every loop run can be analyzed via SQLite without opening raw files first.
2. Deep-dive raw evidence remains available locally (and optionally via Gitea links).

Verification:
1. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b --iterations 1`
2. Query:
   - `workspace/observability/live_acceptance_loop.db`
   - per-run `acceptance_pipeline_live.db` (`run_ledger`)

P0 Operational cadence:
1. Run loop batch.
2. Extract top two failure patterns by count.
3. Patch only one behavior mechanism at a time (prompt contract or guard policy).
4. Re-run same batch and compare deltas.
5. Keep change only if metrics improve.

P0 exit criteria:
1. Baseline model set achieves >= 80% full-chain completion (`REQ -> ARC -> COD -> REV -> guard`) for two consecutive batches.
2. `turn_non_progress` is < 5% overall and < 10% on any single role in baseline set.
3. Guard rationale-empty rejections are zero.
4. No uninstalled-model routing failures in batch logs.

### Phase P1: Make Canonical Assets Runnable
Objective: ensure repo-native assets can execute without test-only scaffolding.
Status: In progress.

Work:
1. [ ] Create/update canonical role files in `model/core/roles/` for all roles required by canonical teams.
2. [ ] Repair team-role references in `model/core/teams/*.json`.
3. [ ] Repair epic-team-seat references in `model/core/epics/*.json`.
4. [ ] Add CI integrity gate for asset references:
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
Status: In progress.

Work:
1. [x] Keep one deterministic fixture test for engine behavior.
2. [ ] Add canonical-asset acceptance test that loads repo model assets directly.
3. [x] Ensure the canonical test validates:
   - seat/role order
   - expected artifacts
   - guard terminal decision by `integrity_guard`
   - all chain issues must reach `DONE` (not `BLOCKED`) in live acceptance
4. [~] Rename pipeline test internals from `developer` to `coder` where contract requires it.
   - Canonical flow paths are now `coder`.
   - Legacy test fixtures still contain `developer` in non-canonical lanes.

Done when:
1. Acceptance lane fails if `coder` step is missing/replaced.
2. Acceptance lane fails if canonical assets are inconsistent.

Verification:
1. `python -m pytest tests/live/test_system_acceptance_pipeline.py -q`
2. `python -m pytest tests/integration/test_system_acceptance_flow.py -q`

### Phase P3: Boundary Enforcement That Matches Reality
Objective: enforce volatility boundaries without loopholes.
Status: Mostly complete (maintain + tighten where needed).

Work:
1. [~] Extend boundary checks to detect adapter coupling through root facades (not only direct `orket.adapters.*` imports).
2. [~] Reduce legacy bridge usage from runtime orchestration paths (`orket.orket` compatibility hops).
3. [x] Keep `scripts/check_volatility_boundaries.py` as pre-merge gate.

Done when:
1. Application layer cannot depend on adapters indirectly through umbrella modules without explicit allowlist.
2. Boundary script catches intentional violation in a red test.

Verification:
1. `python scripts/check_volatility_boundaries.py`
2. `python -m pytest tests/platform/test_architecture_volatility_boundaries.py -q`

### Phase P4: Documentation Reset
Objective: docs become reliable for human/agent execution.
Status: In progress.

Work:
1. [ ] Rewrite stale architecture docs to match current module layout.
2. [ ] Update process docs with current module paths and commands.
3. [ ] Remove or archive historical docs that conflict with current runtime.

Done when:
1. No critical doc references point to removed or relocated runtime paths.
2. New contributor can run acceptance gate without tribal knowledge.

Verification:
1. `rg -n "orket/services/|orket/infrastructure/|orket/orchestration/orchestrator.py|orket/tool_families/" docs ARCHITECTURE.md`
2. Manual runbook dry-run by following docs only.

## Observed Repeatable Patterns (From Live Loop + Run Ledger)
1. Requirements turn fails on progress contract with some models:
   - model emits `write_file` only, omits `update_issue_status(code_review)`.
   - signal: `turn_corrective_reprompt` followed by `turn_non_progress`.
2. Integrity guard blocks too early:
   - architect output passes parser/tool contract but gets blocked with minimal rationale.
   - downstream propagation blocks `COD-1` and `REV-1`.
3. Model capability/compat mismatch is repeatable:
   - uninstalled model tags produce immediate `ModelConnectionError` failures.
4. Raw artifact volume is useful right now:
   - keep `.pytest_live_loop/` for diagnosis.
   - do not track in git (ignored at folder level).
5. Storage strategy now stable:
   - aggregate loop results in `workspace/observability/live_acceptance_loop.db`.
   - run-level summary/artifact refs in `run_ledger`.
   - raw artifacts optionally exported to Gitea when configured.

## Items No Longer Relevant
1. Treating `benchmarks/results/*.json` as the primary loop record.
   - JSON output is now optional export (`--output-json`), not system of record.
2. Expecting acceptance progress from role name `developer` in canonical flow.
   - canonical contract is `coder`; `developer` references are legacy fixtures only.

## Weekly Execution Cadence
1. Monday: pick one blocking failure from P1/P2.
2. Midweek: ship smallest fix + test.
3. Friday: run full gates and record status.

Required weekly proof:
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python scripts/run_live_acceptance_loop.py --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. Query latest batch in `workspace/observability/live_acceptance_loop.db` for pass/fail + pattern counts.

## Exit Criteria
All must be true for two consecutive runs:
1. Canonical acceptance pipeline passes with repo-native assets and exact role chain (`requirements_analyst -> architect -> coder -> code_reviewer -> integrity_guard`).
2. No model asset reference integrity failures.
3. Boundary checks pass without manual exceptions.
4. Docs match runtime paths and operational commands.
