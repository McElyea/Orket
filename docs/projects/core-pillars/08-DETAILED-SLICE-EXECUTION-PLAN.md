# Core Pillars Detailed Slice Execution Plan

Date: 2026-02-24  
Status: active  
Execution policy: slice-first, deterministic gates first

## Objective
Define the canonical, deterministic slice execution order for `core-pillars` with clear DoR/DoD, gates, and bounded scope controls.

## Purpose
This file is the canonical implementation sequence for `core-pillars`.

Use this when the instruction is "follow roadmap" and no project is specified.
This plan is intentionally operational and removes ambiguity about ordering, entry criteria, exit criteria, and gates.

## Rule of Execution
1. Implement by slice, not by pillar batch.
2. Do not start the next slice until the current slice exit criteria are met.
3. Mutating command work must always be built on transaction-shell safety contracts.
4. Replay remains bounded to artifact recording/comparison in CP-2 and must not become a cross-feature policy engine.

## Global Invariants (All Slices)
1. Safety loop for mutating commands:
- plan -> confirm -> snapshot -> execute -> verify -> finalize/revert

2. Scoped write barrier:
- writes only within user scope and computed touch set
- out-of-scope writes hard fail

3. Deterministic verification:
- local verification commands (typecheck/lint/tests) are deterministic and explicit

4. Architecture governance:
- no dependency-direction violations
- no unknown module classifications
- contract-delta governance for intentional boundary breaks

## Slice Map (Canonical Order)

### CP-1.1 Transaction Shell Foundation (active first)
Objective:
Land the safety physics once so every later feature is born safe.

In scope:
1. Transaction runner for mutating commands.
2. Git snapshot/revert strategy.
3. Scoped write barrier enforcement layer.
4. Verify profile execution (`orket.config` driven).
5. Stable safety error-code path.
6. Dry-run touch-set display for mutating commands.

Out of scope:
1. Multi-framework generation.
2. Replay orchestration.
3. Memory intelligence.

Implementation tasks:
1. Add/confirm command operation lifecycle abstraction.
2. Add snapshot adapter with deterministic rollback.
3. Add write policy adapter (`scope + touch set`).
4. Add verify runner with captured output tail.
5. Ensure fail-closed behavior on verify failure.
6. Standardize error-code emissions.
7. Add acceptance tests:
- A1 repo restored on verify failure
- A2 scope barrier hard-fail
- A4 deterministic rollback path

Exit criteria:
1. A1/A2/A4 tests pass.
2. Repo is pre-run identical after forced verify failure.
3. No write outside scope barrier under adversarial fixture.

Required validation commands:
1. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest -q`

---

### CP-1.2 API Generation First Adapter
Objective:
Implement `orket api add` as the first functional workload that stress-tests safety physics on existing repos.

In scope:
1. One explicitly supported framework adapter for v1.
2. Deterministic route/controller/type generation.
3. Router registration and update logic.
4. Idempotency behavior.
5. Extension-point marker contract.
6. Template-driven route test pack generation.

Out of scope:
1. Generic framework inference across all stacks.
2. Model-generated arbitrary test architectures.

Implementation tasks:
1. Choose and lock first framework adapter.
2. Implement deterministic project-style detector for that adapter.
3. Implement schema parser and type-mapping contract.
4. Implement generator using templates (not freeform synthesis).
5. Implement route registration idempotency.
6. Implement extension region markers and preservation.
7. Implement verification-driven fail-closed behavior (`E_DRAFT_FAILURE` path).
8. Add acceptance tests:
- API-1 deterministic output
- API-2 idempotent rerun
- API-3 extension preservation
- API-4 verify fail -> full revert
- API-5 scope barrier

Exit criteria:
1. API-1..API-5 tests pass.
2. Re-running identical command is no-op with explicit idempotent output.
3. User-edited extension region survives rerun.

Required validation commands:
1. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest -q`

---

### CP-1.3 Minimal Scaffolding Hydration
Objective:
Deliver `orket init` baseline without overextending generation complexity.

In scope:
1. Local blueprint/template hydration.
2. Variable substitution and baseline docs/config output.
3. Optional verification run after generation.

Out of scope:
1. Broad adaptive architecture synthesis.
2. Multi-template intelligence routing.

Implementation tasks:
1. Implement local blueprint registry/path contract.
2. Implement non-interactive and interactive variable input handling.
3. Add baseline README and dev command output.
4. Add verify-on-init default behavior with opt-out.
5. Add deterministic scaffold tests for at least one blueprint.

Exit criteria:
1. Init output is deterministic for identical inputs.
2. Baseline scaffold passes local verify profile.
3. No out-of-scope writes during init execution.

Required validation commands:
1. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest -q`

---

### CP-2.1 Replay Artifact Recorder (Bounded)
Objective:
Add replay recording surfaces without turning replay into central policy control.

In scope:
1. Replay artifact schema for run outputs.
2. Deterministic artifact emission for compare/review use.
3. CI artifact presence checks.

Out of scope:
1. Replay-driven command authorization or orchestration policy changes.
2. Cross-feature replay coupling that alters transaction behavior.

Implementation tasks:
1. Define recorder artifact schema.
2. Emit artifacts for scoped command operations.
3. Add deterministic ordering rules for replay fields.
4. Add artifact contract tests.

Exit criteria:
1. Recorder outputs deterministic payloads.
2. No command behavior changes when recorder is disabled/enabled.
3. Replay remains non-authoritative.

---

### CP-2.2 Replay Comparator and Drift Gates
Objective:
Detect drift deterministically between comparable artifacts.

In scope:
1. Deterministic compare surface.
2. CI drift-gate integration.
3. Human-readable mismatch summaries.

Out of scope:
1. Replay as a policy override engine.

Implementation tasks:
1. Implement stable mismatch-field comparison order.
2. Add drift fail/pass fixtures.
3. Integrate compare checks into quality lane.

Exit criteria:
1. Comparator reports deterministic mismatch ordering.
2. Drift gate fails on intentional mismatch and passes on stable baseline.

---

### CP-2.3 Verified Refactor Integration
Objective:
Use trust artifacts to support refactor confidence, not to replace transaction authority.

In scope:
1. Refactor result parity artifacts.
2. Verification and replay summaries in command output.

Out of scope:
1. Auto-approval based on replay alone.

Implementation tasks:
1. Attach parity evidence to refactor outcomes.
2. Ensure refactor still finalizes only after verify pass.
3. Add regression tests for parity-report generation.

Exit criteria:
1. Refactor flow remains fail-closed.
2. Parity artifacts are deterministic and inspectable.

---

### CP-3.1 Bucket D Failure Lessons Memory
Objective:
Reduce repeat failure loops with advisory memory, without introducing mutable policy logic.

In scope:
1. JSONL failure lesson store.
2. Deterministic regex/heuristic classification.
3. Pre-execution retrieval warnings.
4. Advisory preflight checks.

Out of scope:
1. Autonomous memory-driven code changes.
2. Memory-based scope expansion.

Implementation tasks:
1. Implement lesson writer for verify fail/draft fail.
2. Implement deterministic classifier tag set.
3. Implement retrieval scoring and top-K warnings.
4. Implement advisory preflight checks with optional strict mode.
5. Add D1-D4 acceptance tests.

Exit criteria:
1. D1-D4 pass.
2. Memory warnings are advisory-only by default.
3. No mutation/scope behavior changes caused by memory subsystem.

---

### CP-3.2 Stateful Memory/Agent Integration (Bounded Expansion)
Objective:
Integrate vector memory and persistent utility-agent contracts without destabilizing build/trust layers.

In scope:
1. Memory interface integration boundaries.
2. Utility-agent profile persistence contracts.

Out of scope:
1. Emotional companion positioning.
2. Runtime policy authority transfer to memory/agent layers.

Implementation tasks:
1. Add interface contracts and adapter tests.
2. Validate deterministic retrieval boundaries.
3. Add guardrails for role-bounded access.

Exit criteria:
1. Integration tests pass with deterministic behavior.
2. No cross-layer boundary regressions.

---

### CP-3.3 Local Sovereignty and Offline Matrix
Objective:
Prove local-only operation path for v1 command surface.

In scope:
1. Offline capability matrix.
2. Explicit network toggle behavior.
3. Offline runbook and test lane.

Implementation tasks:
1. Document per-command offline capabilities and degradations.
2. Add offline enforcement tests.
3. Validate no default call-home path.

Exit criteria:
1. Offline matrix tests pass.
2. Default run path requires no remote dependency.

---

### CP-4.1 WorkItem Core Contract and Transition API
Objective:
Replace hard-wired card hierarchy assumptions with a profile-agnostic lifecycle contract.

In scope:
1. Introduce canonical `WorkItem` contract (`id`, `kind`, `parent_id`, `status`, `depends_on`, ownership, refs, metadata, audit fields).
2. Immutable workspace-global string identity contract.
3. Transition API contract as sole lifecycle mutation path.
4. Deterministic transition result envelope and error code schema.

Out of scope:
1. Profile-specific hierarchy semantics.
2. UI-level board/tree presentation choices.

Implementation tasks:
1. Define core `WorkItem` schema and invariants.
2. Define `request_transition(item_id, action, actor, payload)` runtime contract.
3. Define deterministic error set:
- `INVALID_ACTION`
- `DEPENDENCY_UNRESOLVED`
- `APPROVAL_REQUIRED`
- `POLICY_VIOLATION`
- `INVARIANT_FAILED`
4. Add contract tests:
- `test_workitem_transition_requires_action_api`
- `test_executor_cannot_set_status_directly`

Exit criteria:
1. No runtime path mutates lifecycle state outside transition API.
2. Transition errors are deterministic and code-stable.

---

### CP-4.2 Profile System and Legacy Freeze
Objective:
Decouple engine core from hierarchy semantics while preserving current behavior in a profile.

In scope:
1. Freeze existing Rock/Epic/Issue behavior as `legacy_cards_v1`.
2. Introduce profile resolver and runtime binding.
3. Ensure profile state maps to core state classes.

Out of scope:
1. Deleting legacy behavior in this slice.

Implementation tasks:
1. Extract legacy transition/hierarchy rules into `legacy_cards_v1`.
2. Add profile contract interface for hierarchy rules and transition mapping.
3. Add parity tests:
- `test_legacy_cards_profile_parity`

Exit criteria:
1. `legacy_cards_v1` reproduces current lifecycle behavior under existing fixtures.
2. Engine core no longer hardcodes Rock/Epic/Issue assumptions.

---

### CP-4.3 New Default Profile (`project_task_v1`)
Objective:
Ship a simpler default profile with 2-level convention and arbitrary depth support.

In scope:
1. `project_task_v1` profile.
2. Minimal default flow (`new -> ready -> in_progress -> blocked|done -> archived`).
3. Arbitrary depth supported through `parent_id` without core depth limits.

Out of scope:
1. Perfect hierarchy optimization for every team pattern.

Implementation tasks:
1. Implement profile transitions and core-state mapping.
2. Add blocked-transition reason requirement.
3. Add profile tests:
- `test_project_task_profile_core_flow`

Exit criteria:
1. Default profile executes deterministic core flow.
2. Blocked path enforces deterministic reason payload.

---

### CP-4.4 Gate Boundary Consolidation
Objective:
Make lifecycle gates authoritative at transition boundaries.

In scope:
1. Pre-transition gate checks (authorization/dependency/policy).
2. Post-transition checks (invariant/audit).
3. Gate request creation at transition boundary outcomes only.

Out of scope:
1. Executor-level policy branching that changes lifecycle semantics.

Implementation tasks:
1. Move approval and guard lifecycle checks into transition boundary evaluators.
2. Keep executor outcome reporting only.
3. Add boundary tests:
- `test_gate_runs_pre_and_post_transition`

Exit criteria:
1. Gate decisions are enforced at transition boundaries only.
2. Executor no longer owns lifecycle authorization.

---

### CP-4.5 Migration and Cutover Safety
Objective:
Provide deterministic migration from Rock/Epic/Issue artifacts to WorkItem model.

In scope:
1. Mapping rules:
- `Rock -> kind=initiative, parent_id=null`
- `Epic -> kind=project, parent_id=<rock>`
- `Issue -> kind=task, parent_id=<epic>`
2. Audit/history preservation contract.
3. Rollback-safe migration execution with dry-run output.

Implementation tasks:
1. Add migration mapper and dry-run artifact output.
2. Add migration fixtures and lossless assertions.
3. Add migration tests:
- `test_migration_rock_epic_issue_mapping_is_lossless`

Exit criteria:
1. Migration preserves identity and lifecycle history fields.
2. Rollback path is deterministic and documented.
3. Profile switch to `project_task_v1` gated by green parity/migration suite.

## Definition of Ready (Per Slice)
1. Slice objective and scope are explicit.
2. Required contracts/spec docs are present.
3. Acceptance tests are defined before implementation.
4. Validation commands are runnable in current repo state.

## Definition of Done (Per Slice)
1. All slice acceptance tests pass.
2. Full regression gates pass:
- dependency direction
- volatility boundaries
- full pytest sweep
3. Docs updated:
- roadmap priority/status pointer
- slice status notes
4. No boundary-policy regressions introduced.

## Status Tracking Convention
1. Update milestone status in `03-MILESTONES.md` with explicit slice progress.
2. If scope changes, update this file first, then roadmap.
3. Keep requirements files stable; change implementation order only via this plan.
