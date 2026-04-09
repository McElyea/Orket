# ProductFlow Implementation Plan
Last updated: 2026-04-05
Status: Completed
Owner: Orket Core
Lane type: Governed run proof + operator review

## Authority posture

This document is the archived implementation plan for the completed ProductFlow lane.

The paired requirements companion is `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/GOVERNED_RUN_PROOF_AND_OPERATOR_REVIEW_REQUIREMENTS.md`.
That requirements document remains the archived requirements authority for this completed lane while this plan preserves the canonical run, command surfaces, workstream order, and closeout gates that were executed.

The accepted requirements intentionally stop short of freezing a ProductFlow-specific review-package schema in `docs/specs/`.
For that reason, Workstream 0 is a contract-freeze gate.
No runtime implementation slice may claim completion until the durable ProductFlow review-package and walkthrough contracts are extracted into `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md` and `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md` and the resulting authority story is synchronized in `CURRENT_AUTHORITY.md`.

## Source authorities

This plan is bounded by:

1. `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/GOVERNED_RUN_PROOF_AND_OPERATOR_REVIEW_REQUIREMENTS.md`
2. `docs/ROADMAP.md`
3. `docs/ARCHITECTURE.md`
4. `CURRENT_AUTHORITY.md`
5. `docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`
6. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
7. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
8. `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
9. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
10. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
11. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
12. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
13. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`

## Purpose

Turn the accepted ProductFlow requirements bundle into one active execution lane that proves a governed Orket run end to end on an operator-meaningful path.

This lane exists to make one bounded governed run live, inspectable, and replay-reviewable or truthfully blocked:

1. live execution,
2. visible approval pause,
3. same-run approval continuation,
4. packet-1 plus packet-2 truth,
5. one first-class operator review package, and
6. same-run replay review or a truthful replay blocker.

## Lane objective

This lane is complete only when all of the following are true:

1. one approval-gated governed turn-tool `write_file` run executes live on the default `issue:<issue_id>` namespace path,
2. the same run can pause on the bounded approval seam and continue on the same governed run after operator approval,
3. the resulting run emits truthful `FinalTruthRecord`, packet-1, packet-2, effect-lineage, and run-evidence-graph surfaces,
4. an operator can complete the frozen review sequence from one machine-readable review index under `runs/<session_id>/`,
5. replay review for that same run emits first-class determinism claim fields and reports `replay_ready` and `stability_status` truthfully, and
6. the repo contains one bounded walkthrough and one canonical command set for live execution, review-package generation, and replay review.

## Current proof checkpoint

As of 2026-04-05, this lane is complete and archived.

What is already captured on the same canonical governed run:
1. `ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py --json`
2. `python scripts/productflow/build_operator_review_package.py --run-id turn-tool-run:1abd183a:PF-WRITE-1:lead_architect:0001 --json`
3. `python scripts/productflow/run_replay_review.py --run-id turn-tool-run:1abd183a:PF-WRITE-1:lead_architect:0001 --json`

Observed same-run result:
1. live governed execution succeeded on `turn-tool-run:1abd183a:PF-WRITE-1:lead_architect:0001`
2. operator review proof succeeded from `runs/1abd183a/productflow_review_index.json`
3. replay review emitted a truthful blocker on that same run with `replay_ready=false` and `stability_status=not_evaluable`

Additional generic truthful-runtime proof-recorder drift remains outside this bounded lane:
1. `python scripts/governance/record_truthful_runtime_packet1_live_proof.py`, `python scripts/governance/record_truthful_runtime_packet2_repair_live_proof.py`, and `python scripts/governance/record_truthful_runtime_artifact_provenance_live_proof.py` still record failures on their broader Phase C acceptance fixtures.
2. Those recorder families are tracked as standing techdebt rather than ProductFlow closeout blockers because they assert a broader runtime and artifact shape than the bounded ProductFlow governed `write_file` slice.
3. If extra support proof is desired beyond the canonical ProductFlow live, review-package, and replay-review set, it must use a ProductFlow-specific or parameterized proof path bound to `agent_output/productflow/approved.txt` and the same canonical `run_id`.

## Decision lock

The following remain fixed for this lane:

1. the canonical governed run is one approval-gated governed turn-tool `write_file` slice only,
2. the canonical namespace is the default `issue:<issue_id>` path only,
3. `create_issue` remains admitted platform behavior but is explicitly out of the ProductFlow golden path,
4. the golden path is operator approval followed by runtime-owned same-governed-run continuation from the accepted pre-effect checkpoint,
5. deny and other blocked outcomes remain required negative-proof truth but are not the bundle-complete golden path,
6. review artifacts remain evidence-first projection surfaces rooted under the existing `runs/<session_id>/` run root,
7. live proof, review proof, and replay proof all bind to the same canonical run identity,
8. `FinalTruthRecord.result_class`, packet-1 truth classification, and replay/stability status remain separate authorities,
9. any new ProductFlow proof artifact family must carry first-class determinism claim fields rather than relying on mapping-only compatibility debt.

## Canonical governed run freeze

### Canonical run

The canonical ProductFlow run is:

1. one bounded issue-scoped request that reaches the admitted `tool_approval` seam for `write_file`,
2. one operator approval on the existing approval surface,
3. one runtime-owned same-attempt continuation on the already-selected governed run,
4. one emitted `write_file` effect lineage with application-owned side-effect boundaries still visible,
5. one authoritative terminal `FinalTruthRecord`,
6. one review package and one replay-review report emitted for that same run.

### Negative truth that must remain visible

The lane must also preserve truthful non-golden-path outcomes:

1. denial of the `write_file` approval request must remain a visible terminal-stop path for the same governed run,
2. absence of an emitted effect must remain visible as absence rather than being normalized into success,
3. `replay_ready=false`, `stability_status=blocked`, and `stability_status=not_evaluable` remain admissible review truth when the evidence supports them,
4. no secondary easier run may be substituted for replay or review proof.

## Canonical identity and artifact resolution

ProductFlow operator commands are keyed by `--run-id`.

The identity and artifact-resolution contract for this lane is:

1. `run_id` is the canonical identity for live proof, review proof, replay proof, and all ProductFlow claim surfaces.
2. `session_id` is an artifact-root locator only. It never substitutes for `run_id`.
3. Before reading or writing `runs/<session_id>/productflow_review_index.json` or any ProductFlow replay-review artifact, the command must resolve `run_id` to exactly one authoritative `session_id`-rooted artifact family.
4. The normative resolver witness for that binding is the validated `runs/<session_id>/run_summary.json`.
5. Resolution is valid only when that selected `run_summary.json` declares the same `run_id`, and no second candidate root claims that same `run_id`.
6. Workstream 0 must carry that same resolver rule into `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md` unless the spec freeze replaces it with a narrower or stronger witness in the same change and synchronizes `CURRENT_AUTHORITY.md`.
7. Zero matches, multiple matches, or lineage drift between resolved `run_id`, `session_id`, control-plane refs, and review-package members must fail closed rather than normalizing to the nearest run root.
8. `productflow_review_index.json` must carry first-class `run_id`, `session_id`, artifact-root, and resolution-basis fields so an operator can see which artifact family was selected and why.

## Canonical operator surfaces

The target canonical commands for this lane are:

1. live execution:
   - `ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py`
2. review-package generation:
   - `python scripts/productflow/build_operator_review_package.py --run-id <run_id>`
3. replay review:
   - `python scripts/productflow/run_replay_review.py --run-id <run_id>`

These commands are now shipped and were used for closeout proof.
They must remain thin wrappers over shipped runtime seams and existing authority surfaces rather than demo-only bypasses.

Supporting existing authority surfaces that the new commands must reuse include:

1. `python scripts/observability/emit_run_evidence_graph.py --run-id <run_id>`
2. `python scripts/audit/verify_run_completeness.py`
3. `python scripts/audit/replay_turn.py`
4. `python scripts/audit/compare_two_runs.py`

Until the ProductFlow wrappers land, those supporting commands are implementation building blocks, not the canonical operator contract for this lane.

## Stable artifact names to freeze

Before lane closeout, the following names and paths must be live and stable:

1. `runs/<session_id>/productflow_review_index.json`
2. `runs/<session_id>/run_evidence_graph.json`
3. `runs/<session_id>/run_evidence_graph.mmd`
4. `runs/<session_id>/run_evidence_graph.html`
5. `benchmarks/results/productflow/governed_write_file_live_run.json`
6. `benchmarks/results/productflow/operator_review_proof.json`
7. `benchmarks/results/productflow/replay_review.json`

Every new rerunnable JSON result in this lane must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` or `write_json_with_diff_ledger`.

## Workstream order

## Workstream 0 - Contract freeze and walkthrough extraction

### Goal

Extract the durable ProductFlow contract surfaces before runtime implementation widens.

### Tasks

1. Extract the ProductFlow operator review package contract into `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`.
2. Extract the ProductFlow governed-run walkthrough contract into `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`.
3. Record any required contract delta note for the new durable contract surfaces.
4. Freeze the normative `run_id` to `session_id` resolver witness for the ProductFlow review package.
5. Freeze the canonical workload request, expected approval seam, expected emitted artifact, and expected review sequence.
6. Update `CURRENT_AUTHORITY.md` once the durable ProductFlow contract surfaces are real.

### Exact doc surfaces

1. `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/GOVERNED_RUN_PROOF_AND_OPERATOR_REVIEW_REQUIREMENTS.md`
2. `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/PRODUCTFLOW_IMPLEMENTATION_PLAN.md`
3. `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`
4. `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/ROADMAP.md` if any frozen canonical paths change

### Exit criteria

1. the ProductFlow review package has a durable contract authority at `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`,
2. the canonical walkthrough exists as a durable operator-facing authority surface at `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md`,
3. the canonical commands and stable artifact names above are still the single ProductFlow story,
4. no runtime implementation workstream claims success before these contract surfaces exist.

## Workstream 1 - Canonical live governed run

### Goal

Make the bounded approval-gated governed turn-tool `write_file` path executable as one truthful live ProductFlow run.

### Exact runtime and script surfaces

1. `orket/application/workflows/turn_tool_dispatcher.py`
2. `orket/application/workflows/turn_tool_dispatcher_protocol.py`
3. `orket/application/workflows/turn_executor_control_plane_evidence.py`
4. `orket/application/workflows/turn_executor_completed_replay.py`
5. `orket/application/workflows/turn_executor_resume_replay.py`
6. `orket/application/services/governed_turn_tool_approval_continuation_service.py`
7. `orket/application/services/tool_approval_control_plane_operator_service.py`
8. `orket/application/services/turn_tool_control_plane_service.py`
9. `scripts/productflow/run_governed_write_file_flow.py`

### Tasks

1. Add the thin ProductFlow live runner around the shipped issue-scoped governed turn-tool path.
2. Freeze one bounded workload that always reaches exactly one operator-significant `write_file` approval seam.
3. Preserve application-owned side-effect boundaries in emitted truth and proof artifacts.
4. Capture canonical run identity and fail-closed `run_id` to `session_id` linkage so downstream review and replay stay same-run.
5. Record the live-run proof result at `benchmarks/results/productflow/governed_write_file_live_run.json`.
6. Keep denial and other blocked outcomes truthful and visible rather than smoothing them away.

### Required proof

1. `python -m pytest -q tests/application/test_turn_executor_middleware.py -k "write_file_approval_resume_continues_same_governed_run"`
2. `python -m pytest -q tests/application/test_orchestrator_epic.py -k "pending_gate_callback_creates_tool_approval_request"`
3. `ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py`

### Exit criteria

1. the live command reaches a pending `tool_approval` hold for `write_file`,
2. operator approval continues the same governed run from the accepted checkpoint,
3. the run emits a truthful terminal `FinalTruthRecord` plus durable effect lineage,
4. the live proof artifact records observed path, observed result, run identity, and emitted evidence refs without relying on a second easier run.

## Workstream 2 - Operator review package and packet-2 projection

### Goal

Make one machine-readable operator review package that organizes authoritative ProductFlow evidence without becoming a second runtime.

### Exact runtime and script surfaces

1. `orket/runtime/run_summary.py`
2. `orket/runtime/run_summary_packet2.py`
3. `orket/runtime/run_summary_artifact_provenance.py`
4. `orket/runtime/run_graph_reconstruction.py`
5. `scripts/observability/emit_run_evidence_graph.py`
6. `scripts/common/run_summary_support.py`
7. `scripts/productflow/build_operator_review_package.py`

### Tasks

1. Emit `runs/<session_id>/productflow_review_index.json` as the single review-package root or index artifact.
2. Make that review index point at run identity, resolved `session_id`, artifact root, terminal `FinalTruthRecord`, packet-1 surfaces, packet-2 surfaces, effect records, terminal summary projection when present, and replay-review surfaces or blocker records.
3. Expose a first-class approval-continuation evidence block that proves "this exact approval decision resumed this exact governed run from this exact accepted pre-effect checkpoint," including authoritative refs for the approval decision, `control_plane_target_ref`, checkpoint or checkpoint-acceptance lineage, resumed attempt or step lineage, and the first continuation-side effect or terminal-stop evidence.
4. Reuse the existing run-evidence graph artifact family rather than inventing a second run root.
5. Keep packet-2 subordinate to existing runtime truth and preserve absence truth explicitly.
6. Make the review-package command also emit `benchmarks/results/productflow/operator_review_proof.json` showing that the frozen review questions were answerable from the package.

### Required proof

1. `python scripts/productflow/build_operator_review_package.py --run-id <run_id>`

### Exit criteria

1. an operator can answer the frozen review sequence from the package without reading implementation code,
2. an operator can prove from the package that the selected approval decision resumed the selected governed run from the selected accepted pre-effect checkpoint or, on the denial path, terminal-stopped that same run,
3. authoritative artifacts always win over convenience summaries,
4. the review package surfaces `replay_ready` and `stability_status` using existing authority vocabularies rather than a ProductFlow-only enum family,
5. the review proof artifact records which required review questions were answered and which authoritative refs supported those answers.

## Workstream 3 - Replay review and determinism claim surfaces

### Goal

Bind MAR replay review and determinism claim surfaces to the same canonical ProductFlow run.

### Exact runtime and script surfaces

1. `scripts/audit/verify_run_completeness.py`
2. `scripts/audit/replay_turn.py`
3. `scripts/audit/compare_two_runs.py`
4. `scripts/common/run_summary_support.py`
5. `scripts/productflow/run_replay_review.py`

### Tasks

1. Build the ProductFlow replay-review command as a thin wrapper around the existing MAR completeness and replay or compare surfaces.
2. Require the wrapper to bind to the same canonical run id emitted by Workstream 1 and fail closed when that `run_id` cannot be resolved to exactly one authoritative `session_id`-rooted artifact family.
3. Emit `claim_tier`, `compare_scope`, `operator_surface`, `policy_digest`, and `control_bundle_ref` or `control_bundle_hash` as first-class proof fields on any new ProductFlow replay artifact.
4. Record `replay_ready` and `stability_status` truthfully, including explicit blocker classes for `blocked` and evidence gaps for `not_evaluable`.
5. Persist the rerunnable replay-review result at `benchmarks/results/productflow/replay_review.json`.

### Required proof

1. `python scripts/productflow/run_replay_review.py --run-id <run_id>`

### Exit criteria

1. replay review reports the same canonical run identity used by the live and review proofs,
2. stability claims are emitted only when the compare surface supports them,
3. blocked or not-yet-evaluable states remain explicit and do not masquerade as stable replay proof.

## Workstream 4 - Lane proof, authority sync, and closeout readiness

### Goal

Close the lane only after one real ProductFlow run proves the whole story together and the supporting authority surfaces remain synchronized.

### Tasks

1. Run the canonical live execution command.
2. Run the canonical review-package generation command for that same run.
3. Run the canonical replay-review command for that same run.
4. Rerun supporting approval-checkpoint and run-evidence-graph proof or regression surfaces when touched code or contract slices overlap those authorities.
5. Synchronize `CURRENT_AUTHORITY.md`, `docs/ROADMAP.md`, the extracted ProductFlow specs, and any operator-facing runbook material touched by the lane.
6. Refuse closeout if any command, artifact path, or proof field remains placeholder-only.

### Supporting regression commands

1. `python -m pytest -q tests/interfaces/test_api_approvals.py tests/application/test_engine_approvals.py`
2. `python -m pytest -q tests/scripts/test_emit_run_evidence_graph.py tests/contracts/test_run_evidence_graph_contract.py tests/contracts/test_run_evidence_graph_projection_validation.py`

### Closeout gate

This lane may close only when one canonical ProductFlow run proves all of the following together:

1. live governed execution,
2. visible approval seam,
3. same-run continuation,
4. truthful terminal closure,
5. review-package answerability,
6. same-run replay review or truthful replay blocker.

## Explicit non-goals

This lane does not authorize:

1. broad ControlPlane convergence reopening,
2. a second ProductFlow golden path,
3. generic UI work divorced from the emitted review package,
4. provider-breadth expansion beyond what the canonical governed run needs,
5. promotion of `create_issue` into the primary lane without an explicit roadmap change.
