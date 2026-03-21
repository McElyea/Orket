# RG03182026 Phase 1 Runtime Gap Requirements

Last updated: 2026-03-18
Status: Archived (requirements satisfied)
Owner: Orket Core
Lane type: Techdebt runtime gap remediation

Archive note:
1. Completed and archived on 2026-03-18.
2. Closeout authority: [docs/projects/archive/techdebt/RG03182026/Closeout.md](docs/projects/archive/techdebt/RG03182026/Closeout.md)

## Purpose

Define the bounded remediation contract for the runtime gaps surfaced by Phase 1 in [docs/projects/future/game-plan.md](docs/projects/future/game-plan.md).

This lane exists to resolve four truth gaps only:

1. the current cards runtime path is implicit and app-centric rather than explicitly selected
2. the current `coder` path is hard-wired to `agent_output/main.py`
3. the current cards run summary does not expose a canonical `stop_reason`
4. the current ODR path is unstable on live local models, does not yet force semantically valid requirement decisions, and is not wired into the cards executor path

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/ARCHITECTURE.md`
6. [docs/projects/future/game-plan.md](docs/projects/future/game-plan.md)
7. [scripts/probes/p01_single_issue.py](scripts/probes/p01_single_issue.py)
8. [scripts/probes/p02_odr_isolation.py](scripts/probes/p02_odr_isolation.py)
9. [scripts/probes/p03_epic_trace.py](scripts/probes/p03_epic_trace.py)
10. [scripts/probes/p04_odr_cards_integration.py](scripts/probes/p04_odr_cards_integration.py)
11. [orket/application/workflows/orchestrator_ops.py](orket/application/workflows/orchestrator_ops.py)
12. [orket/decision_nodes/builtins.py](orket/decision_nodes/builtins.py)
13. [orket/application/services/prompt_compiler.py](orket/application/services/prompt_compiler.py)
14. [orket/application/services/canonical_role_templates.py](orket/application/services/canonical_role_templates.py)
15. [orket/application/workflows/turn_path_resolver.py](orket/application/workflows/turn_path_resolver.py)
16. [orket/application/workflows/turn_contract_validator.py](orket/application/workflows/turn_contract_validator.py)
17. [orket/application/workflows/turn_corrective_prompt.py](orket/application/workflows/turn_corrective_prompt.py)
18. [orket/application/services/deployment_planner.py](orket/application/services/deployment_planner.py)
19. [orket/kernel/v1/odr/core.py](orket/kernel/v1/odr/core.py)
20. [orket/kernel/v1/odr/parsers.py](orket/kernel/v1/odr/parsers.py)
21. [orket/kernel/v1/odr/leak_policy.py](orket/kernel/v1/odr/leak_policy.py)
22. [benchmarks/results/odr/odr_7b_baseline.json](benchmarks/results/odr/odr_7b_baseline.json)

## Current Truth

1. `small_project_builder_variant=auto` currently resolves to `coder`; `auto` is not a third runtime path.
2. small-project execution requires a `code_reviewer` seat at preflight, but current live probe traffic still routed the successful Phase 1 single-issue run through `coder` then `integrity_guard`.
3. the current cards runtime is app-centric:
   1. `prompt_compiler` instructs `coder` and `developer` to write `agent_output/main.py`
   2. `required_write_paths_for_seat()` requires `agent_output/main.py` for `coder` and `developer`
   3. reviewer and guard read-path contracts also assume `agent_output/main.py`
   4. deployment planner scaffolds `python agent_output/main.py`
4. Phase 1 probe P-01 succeeded live only because the model wrote `agent_output/main.py`, not the requested `agent_output/fibonacci.py`.
5. Phase 1 probe P-03 failed live with `GovernanceViolation` because a request for `agent_output/schema.json` violated the current `coder` write-path contract after corrective reprompt.
6. Phase 1 probe P-02 showed live ODR instability on `qwen2.5-coder:7b`: `STABLE_DIFF_FLOOR` once, `FORMAT_VIOLATION` four times, and no `CODE_LEAK` hard stops.
7. Local ODR baseline artifacts already show a semantic failure mode on `missing_constraint`: required retention and encryption constraints were allowed to drift into vague requirement prose, `ASSUMPTIONS`, and `OPEN_QUESTIONS`, and later auditor guidance tolerated or reinforced that demotion instead of forcing an explicit decision or a stricter rewrite.
8. Phase 1 probe P-04 found no ODR fingerprints in cards-engine observability artifacts and no targeted cards-path code references to `run_round`, `ReactorConfig`, `ReactorState`, `history_rounds`, or `CODE_LEAK`.
9. the current cards run summary does not expose a canonical `stop_reason`.

## Closeout Result

Resolved on 2026-03-18.

1. `builder_guard_app_v1`, `builder_guard_artifact_v1`, and `odr_prebuild_builder_guard_v1` are now explicit runtime choices.
2. Live P-01 app/artifact runs and live P-03 artifact runs completed against truthful artifact contracts, and cards run summary now exposes canonical `stop_reason`.
3. The five-run live P-02 baseline returned `UNRESOLVED_DECISIONS` in all five runs with one raw signature and no unexpected hard `CODE_LEAK` or repeated format failure.
4. Live P-04 distinguished non-ODR cards runs from ODR-enabled cards runs through direct cards artifacts and summary fields, including `odr_active`, `odr_valid`, `odr_pending_decisions`, and `odr_artifact_path`.
5. The explicit ODR/cards path remains non-default; accepted `MAX_ROUNDS` outcomes can continue when `odr_valid=true`, `odr_pending_decisions=0`, and `odr_accepted=true`, while non-accepted outcomes remain fail-closed.
6. Auditor `REWRITE` patches are advisory unless they surface governed semantic invalidity, unresolved required decisions, contradiction, required-constraint regression, or another explicit blocking signal.

## Resolution Goal

This lane is complete only when Orket can truthfully do all of the following:

1. name the current app-centric cards path as an explicit execution choice
2. route non-app artifact work through a truthful artifact contract instead of a hidden `main.py` assumption
3. emit a canonical cards `stop_reason`
4. run a live ODR baseline with materially lower format fragility and semantically governed convergence
5. expose an explicit, observable ODR/cards integration path instead of an unwired implication

## Scope

In scope:

1. execution-profile naming and runtime disclosure
2. explicit artifact-contract support for cards issues and epics
3. contract alignment across prompt compilation, seat routing, read/write validation, corrective prompts, and deployment planning
4. cards run-summary and observability additions needed to report execution-profile and `stop_reason`
5. ODR prompt-shape hardening, parser handling, semantic validity enforcement, auditor enforcement, leak-policy calibration, and convergence reporting
6. explicit ODR/cards integration as a bounded stage or profile
7. probe and targeted-test updates needed to prove the above

Out of scope:

1. a broad orchestrator redesign unrelated to the Phase 1 runtime gaps
2. duplicate canonical builder roles that only copy `coder` behavior under a new name
3. broad workload expansion beyond the Phase 1 probe surfaces
4. silent relaxation of contracts that hides failures instead of recording them

## Card Choice Requirements

### Current Choice

1. Orket must name the current implicit small-project path as `builder_guard_app_v1`.
2. `builder_guard_app_v1` must truthfully mean:
   1. builder turns are routed to the configured builder seat and currently default to `coder`
   2. a review-capable seat must still exist in the team surface
   3. terminal completion is guard-enforced
   4. the primary implementation artifact is `agent_output/main.py`
   5. app-oriented deployment assumptions are allowed
3. If a run uses this profile, runtime events and run summary must say so explicitly.

### What This Lane Must Work Into

1. Orket must add `builder_guard_artifact_v1`.
2. `builder_guard_artifact_v1` must drive required read and write paths from an explicit artifact contract declared on the issue or epic.
3. `builder_guard_artifact_v1` must not inherit `agent_output/main.py` requirements unless the artifact contract declares that path.
4. Orket may later add a broader staged profile such as `full_pipeline_v1`, but that is not required for this lane.
5. Orket must add an explicit ODR-backed profile or stage named separately from the non-ODR cards path; this lane must not hide ODR behind the same profile name.

## Coder Path Requirements

### Allowed End-State Choices

1. Recommended end state:
   1. keep `coder` as the canonical builder role
   2. make its required paths profile-driven through one artifact-contract source of truth
   3. keep `agent_output/main.py` as the default only for `builder_guard_app_v1`
2. Acceptable interim truth during implementation:
   1. preserve the current `builder_guard_app_v1` contract as-is
   2. fail closed before execution when a non-app task tries to use the app profile

### Disallowed Choice

1. Do not add a duplicate `artifact_builder`, `schema_builder`, or similar shim role that merely reproduces `coder` behavior under another canonical name without a materially different responsibility boundary.

### Artifact Contract Requirements

1. The repo must have one authoritative artifact-contract shape for cards execution.
2. That artifact contract must be the source of truth for:
   1. prompt compiler write-path instructions
   2. required read paths
   3. required write paths
   4. corrective prompt path reminders
   5. reviewer and guard read surfaces
   6. deployment-planner entrypoint assumptions
3. The artifact contract must support at minimum:
   1. required write paths
   2. required read paths
   3. optional primary entrypoint
   4. artifact kind or execution intent sufficient to distinguish app-like work from non-app artifact work
4. The cards runtime must record both:
   1. the requested artifact contract
   2. the observed artifact outputs
5. If the runtime coerces a requested seat, profile, or artifact path, that coercion must be recorded in run observability.

## Cards Stop-Reason Requirements

1. The cards run summary must expose a canonical `stop_reason` field.
2. `stop_reason` must be present even when the value is `null`.
3. Deterministic post-corrective contract failures must map to stable `stop_reason` values rather than being visible only through free-form error strings.

## ODR Requirements

### Hardening Requirements

1. ODR prompt shape, parser acceptance, leak gating, and convergence logic must remain separate governed surfaces.
2. Every ODR stop must preserve:
   1. raw architect output
   2. raw auditor output
   3. parse errors, if any
   4. leak-detection trace fields
   5. final stop reason
3. Format-invalid rounds must not count toward convergence.
4. Weak-token observations such as `type` alone must remain warnings, not hard `CODE_LEAK` stops.
5. If parser repair or normalization is introduced, it must be:
   1. deterministic
   2. explicitly recorded
   3. attributable to a named repair class
   4. accompanied by preservation of the original raw output
6. Silent fuzzy parsing that changes meaning without a recorded repair is not allowed.

### Requirement Validity Requirements

1. ODR must evaluate architect outputs against a governed semantic validity contract separate from format parsing.
2. A round is semantically valid only if its `REQUIREMENT` section is:
   1. deterministic
   2. non-contradictory
   3. testable
   4. explicit about required bounds or decision placeholders
3. Required constraints must appear in `REQUIREMENT`. `ASSUMPTIONS` and `OPEN_QUESTIONS` are explanatory surfaces only and must not carry required behavior, required numeric bounds, required security controls, or required retention controls.
4. If a required value is missing from context, `REQUIREMENT` must carry an explicit field-scoped `DECISION_REQUIRED` marker. An unresolved `DECISION_REQUIRED` may remain observable during refinement, but it must block successful convergence and final success classification until resolved or fail closed under a governed fallback rule.
5. Requirement text that preserves unresolved behavior alternatives such as `either`, `or`, `may`, `depending on`, or equivalent compromise language is invalid unless tied to a governed decision field with explicit selection semantics.
6. Accepted rounds must not demote a previously required constraint into `ASSUMPTIONS` or `OPEN_QUESTIONS`.
7. Accepted rounds must not remove a required constraint unless it is replaced by a stricter or explicitly superseding requirement.
8. Format-valid but semantically invalid rounds must not count toward convergence.
9. Stable repetition of a semantically invalid output must stop with `INVALID_CONVERGENCE`.
10. Reaching max rounds with unresolved required decisions must stop with `UNRESOLVED_DECISIONS`.

### Auditor Enforcement Requirements

1. Auditor patches must use governed patch classes:
   1. `ADD`
   2. `REMOVE`
   3. `REWRITE`
   4. `DECISION_REQUIRED`
2. A `DECISION_REQUIRED` patch must record:
   1. target field or policy
   2. required value class and units if applicable
   3. allowed options or governed fallback rule if one exists
3. When auditor emits `DECISION_REQUIRED`, the next architect round must either:
   1. resolve it in `REQUIREMENT`, or
   2. preserve it as an explicit `REQUIREMENT`-level `DECISION_REQUIRED` marker
4. Auditor must reject outputs that:
   1. introduce contradiction
   2. preserve unresolved mandatory alternatives
   3. demote required constraints into `ASSUMPTIONS` or `OPEN_QUESTIONS`
   4. introduce hallucinated constants
   5. remove required constraints without stronger replacement
5. Auditor must not recommend removing a required constraint solely to reduce contradiction pressure; contradiction must be resolved by a governed decision or stricter rewrite.
6. ODR trace artifacts must preserve per round:
   1. patch classes
   2. validity verdict
   3. pending decision count
   4. contradiction count

### Live-Baseline Requirements

1. ODR must have one canonical live baseline command for the current local provider/model.
2. The canonical five-run baseline must materially improve over the Phase 1 result.
3. For this lane, materially improve means:
   1. no more than one `FORMAT_VIOLATION` in five canonical live runs
   2. no unexpected hard `CODE_LEAK` stop on legitimate requirements discussion
   3. every stop reason is classified directly from governed parser or convergence logic, not ad-hoc caller interpretation

## ODR/Cards Integration Requirements

1. ODR must not be described as part of the cards path until the cards runtime emits ODR artifacts directly.
2. The first required integration path is an explicit pre-build refinement stage or profile, not a hidden rewrite of every cards turn.
3. When that path is active, the cards runtime must emit:
   1. `odr_active=true`
   2. `history_rounds` or a dedicated ODR artifact reference
   3. ODR `stop_reason`
   4. the accepted refined requirement or explicit ODR failure result
   5. `odr_valid`
   6. `odr_pending_decisions`
4. When the normal non-ODR cards path is active, the runtime must emit `odr_active=false`.
5. The integration path must be observable from both:
   1. cards observability artifacts
   2. cards run summary or equivalent canonical summary artifact

## Verification Requirements

### Structural Proof

1. Add or update targeted structural tests for:
   1. execution-profile selection and disclosure
   2. artifact-contract path derivation
   3. reviewer and guard path derivation under both app and artifact profiles
   4. cards `stop_reason` reporting
   5. ODR parser and leak-policy behavior
   6. requirement-validity and `DECISION_REQUIRED` propagation behavior
   7. rejection of constraint demotion into `ASSUMPTIONS` or `OPEN_QUESTIONS`
   8. `INVALID_CONVERGENCE` and `UNRESOLVED_DECISIONS` classification
   9. auditor patch classification and monotonicity
   10. ODR/cards integration-path observability, including `odr_valid` and `odr_pending_decisions`

### Live Proof

1. Non-sandbox live proof for this lane must set `ORKET_DISABLE_SANDBOX=1`.
2. Canonical live proof for the cards path must include:
   1. P-01 on the app profile
   2. P-01 on the artifact profile
   3. P-03 on the artifact profile
   4. P-04 against both a non-ODR cards run and an ODR-enabled cards run
3. Canonical live proof for ODR must include the five-run P-02 baseline.

## Conclusive Gate

This lane is conclusive only when all of the following are true:

1. the current app-centric cards behavior is exposed as `builder_guard_app_v1`
2. a non-app artifact cards path exists as `builder_guard_artifact_v1`
3. artifact-profile live runs no longer fail because `coder` is hard-wired to `agent_output/main.py`
4. the cards run summary exposes canonical `stop_reason`
5. the ODR canonical five-run live baseline satisfies the lane live-baseline requirements
6. an explicit ODR/cards integration path emits ODR artifacts, `odr_active=true`, `odr_valid`, and `odr_pending_decisions`
7. the non-ODR cards path emits `odr_active=false`
8. `python scripts/governance/check_docs_project_hygiene.py` passes

## Residual Truth Rule

If the lane cannot achieve the ODR live-baseline target without unsafe relaxation:

1. keep ODR out of the default cards path
2. leave ODR as an explicit non-default profile or stage only
3. update active docs in the same change to say that ODR is not yet default-ready
4. do not describe that narrowed outcome as a full ODR stabilization win
