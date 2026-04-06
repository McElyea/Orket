# ProductFlow Operator Review Package V1

Last updated: 2026-04-05
Status: Active
Owner: Orket Core

## Purpose

Freeze the durable operator-review contract for the canonical ProductFlow governed `write_file` proof lane.

This contract defines:
1. the canonical ProductFlow run identity,
2. the fail-closed `run_id` to `session_id` resolver witness,
3. the stable review-package artifact family,
4. the frozen operator review sequence, and
5. the proof contract for the machine-readable review package.

## Canonical Scope

The ProductFlow review package covers one bounded governed path only:
1. one governed turn-tool run,
2. one `approval_required_tool:write_file` approval seam,
3. one operator approval on the existing approval surface,
4. one same-governed-run continuation from the accepted pre-effect checkpoint,
5. one emitted `write_file` artifact path, and
6. one same-run replay-review surface or truthful replay blocker.

No second ProductFlow golden path is admitted under this contract.

## Canonical Commands

1. Live execution: `ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py`
2. Review package: `python scripts/productflow/build_operator_review_package.py --run-id <run_id>`
3. Replay review: `python scripts/productflow/run_replay_review.py --run-id <run_id>`

These commands are thin wrappers over shipped runtime and audit seams.
They are the only admitted ProductFlow operator paths for this lane.

## Canonical Identity And Resolver

1. `run_id` is the canonical ProductFlow identity and must be the governed turn-tool run id.
2. `session_id` is an artifact-root locator only and never substitutes for `run_id`.
3. ProductFlow review and replay commands must fail closed unless they can resolve `run_id` to exactly one authoritative `runs/<session_id>/` artifact family.
4. The normative resolver witness is:
   - one unique approval row with `control_plane_target_ref == <run_id>`,
   - that same approval row carrying `reason == approval_required_tool:write_file`,
   - plus a validated `runs/<session_id>/run_summary.json` for the same session root.
5. For the canonical ProductFlow fixture, `run_summary.run_id` is the session id and `run_summary.control_plane.run_id` is the cards-epic run id. Neither field replaces the governed turn-tool `run_id`.
6. Zero matches, multiple matches, or drift between the selected approval row, `run_id`, `session_id`, and validated run-summary root are contract failures.

## Stable Artifact Family

The ProductFlow review surface is frozen to the following stable paths:
1. `runs/<session_id>/productflow_review_index.json`
2. `runs/<session_id>/run_evidence_graph.json`
3. `runs/<session_id>/run_evidence_graph.mmd`
4. `runs/<session_id>/run_evidence_graph.html`
5. `benchmarks/results/productflow/governed_write_file_live_run.json`
6. `benchmarks/results/productflow/operator_review_proof.json`
7. `benchmarks/results/productflow/replay_review.json`

Any rerunnable JSON artifact in this family must use the diff-ledger writers from `scripts.common.rerun_diff_ledger`.

## Review Index Contract

`runs/<session_id>/productflow_review_index.json` is the single review-package root.

It must carry, at minimum:
1. `schema_version`, `generated_at_utc`, `run_id`, `session_id`, and `artifact_root`
2. `resolution_basis`
3. a validated `run_summary` reference and summary block
4. `terminal_final_truth`
5. `packet1`
6. `packet2`
7. `artifact_provenance`
8. `approval_continuation_evidence`
9. `run_evidence_graph`
10. `replay_review`
11. `review_questions`

## Approval Continuation Evidence Contract

The review package must prove "this exact approval decision resumed this exact governed run from this exact accepted pre-effect checkpoint" with first-class fields for:
1. `approval_id`
2. `approval_status`
3. `control_plane_target_ref`
4. `target_run`
5. `target_checkpoint`
6. `target_effect_journal`
7. `target_resource`
8. `target_reservation`
9. `target_operator_action`
10. `target_final_truth`

Authoritative target-side control-plane surfaces win over convenience summaries.

## Frozen Review Sequence

The ProductFlow review package must let an operator answer these questions without reading implementation code:
1. What run is this?
2. What was requested?
3. What path did the runtime take?
4. What action or effect was governed?
5. What terminal closure truth was assigned?
6. Which packet-1 truth classifications applied?
7. Is the run replay-ready and what is its stability status?

## Review Proof Contract

`benchmarks/results/productflow/operator_review_proof.json` is the review-package proof surface.

It must:
1. identify the same `run_id` and `session_id` used by the live proof,
2. point at `review_index_path`,
3. record `answered_question_count` and `required_question_count`,
4. list `unanswered_questions`,
5. expose `replay_ready` and `stability_status`, and
6. map each review question to authoritative supporting refs.

`observed_result=success` is valid only when the frozen review questions are answerable from the package and the run-evidence graph is not blocked.

## Truth Rules

1. The review package is evidence-first and does not become a second runtime.
2. `FinalTruthRecord.result_class`, packet-1 truth classification, and replay or stability status remain separate authorities.
3. Absence truth must stay explicit. Missing replay evidence, missing emitted effects, or missing qualifying closure outputs must remain visible as absence.
4. Replay surfaces may report a truthful blocker for the same canonical run; they may not silently swap to an easier run.

## Sources

1. `docs/specs/RUN_EVIDENCE_GRAPH_V1.md`
2. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
3. `docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md`
4. `docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md`
5. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
6. `scripts/productflow/productflow_support.py`
7. `scripts/productflow/build_operator_review_package.py`
8. `scripts/productflow/run_replay_review.py`
9. `scripts/observability/emit_run_evidence_graph.py`
