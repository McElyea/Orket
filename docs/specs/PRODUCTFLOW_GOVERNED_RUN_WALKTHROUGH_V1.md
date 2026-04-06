# ProductFlow Governed Run Walkthrough V1

Last updated: 2026-04-05
Status: Active
Owner: Orket Core

## Purpose

Provide the canonical operator walkthrough for the bounded ProductFlow governed `write_file` proof path.

This walkthrough is the single admitted ProductFlow story for:
1. live governed execution,
2. visible approval pause,
3. same-run approval continuation,
4. operator review package generation, and
5. same-run replay review or truthful replay blocker.

## Preconditions

1. The repo is installed with the normal development bootstrap.
2. This walkthrough is not sandbox-acceptance work, so the live proof command must run with `ORKET_DISABLE_SANDBOX=1`.
3. The canonical workspace root is `workspace/productflow`.
4. The canonical bounded output artifact is `agent_output/productflow/approved.txt`.

## Canonical Run

The bounded ProductFlow run is one issue-scoped governed turn-tool `write_file` slice only:
1. epic id: `productflow_governed_write_file`
2. issue id: `PF-WRITE-1`
3. builder seat: `lead_architect`
4. approval seam: `approval_required_tool:write_file`
5. emitted artifact: `agent_output/productflow/approved.txt`
6. terminal issue status: `done`

## Step 1: Live Governed Execution

Run:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/productflow/run_governed_write_file_flow.py
```

Expected outcome:
1. the command reaches one visible pending `tool_approval` hold for `write_file`
2. the operator approval is applied on the shipped approval surface
3. continuation resumes the same governed run from the accepted pre-effect checkpoint
4. `benchmarks/results/productflow/governed_write_file_live_run.json` records `observed_result=success`
5. the live proof artifact exposes the canonical `run_id` and `session_id`
6. `workspace/productflow/agent_output/productflow/approved.txt` exists and contains `approved`

## Step 2: Operator Review Package

Take `run_id` from `benchmarks/results/productflow/governed_write_file_live_run.json` and run:

```text
python scripts/productflow/build_operator_review_package.py --run-id <run_id>
```

Expected outcome:
1. `runs/<session_id>/productflow_review_index.json` is emitted
2. the same run emits `runs/<session_id>/run_evidence_graph.json`
3. the same run emits `runs/<session_id>/run_evidence_graph.mmd`
4. the same run emits `runs/<session_id>/run_evidence_graph.html`
5. `benchmarks/results/productflow/operator_review_proof.json` records `observed_result=success`

The review package must answer the frozen review sequence from machine-readable evidence alone.

## Step 3: Replay Review

Use the same `run_id` and run:

```text
python scripts/productflow/run_replay_review.py --run-id <run_id>
```

Expected outcome on the current bounded fixture:
1. `benchmarks/results/productflow/replay_review.json` is emitted for the same `run_id`
2. the replay surface truthfully reports `replay_ready=false`
3. the replay surface truthfully reports `stability_status=not_evaluable`
4. the replay surface truthfully reports `claim_tier=non_deterministic_lab_only`
5. the replay surface remains a same-run truthful blocker rather than a stable replay claim

The current canonical ProductFlow fixture is expected to surface these `missing_evidence` items:
1. `agent_output/main.py`
2. `agent_output/verification/runtime_verification.json`
3. `no_authoritative_contract_verdict_surface`

If those missing-evidence requirements change, this walkthrough and `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md` must be updated in the same change.

## Frozen Review Sequence

After the live run completes, the operator review sequence is:
1. identify the governed `run_id`
2. confirm what was requested from the approval payload
3. inspect the run-evidence graph for the runtime path
4. inspect the approval continuation evidence block for the governed action and checkpoint lineage
5. inspect the target-side `FinalTruthRecord`
6. inspect packet-1 and packet-2 review fields
7. inspect replay-ready and stability status from the replay-review surface

## Stable Artifact Summary

1. Live proof: `benchmarks/results/productflow/governed_write_file_live_run.json`
2. Review index: `runs/<session_id>/productflow_review_index.json`
3. Review proof: `benchmarks/results/productflow/operator_review_proof.json`
4. Replay review: `benchmarks/results/productflow/replay_review.json`
5. Review graph JSON: `runs/<session_id>/run_evidence_graph.json`
6. Review graph Mermaid: `runs/<session_id>/run_evidence_graph.mmd`
7. Review graph HTML: `runs/<session_id>/run_evidence_graph.html`

## Identity Note

The canonical ProductFlow `run_id` is the governed turn-tool run id from the live proof artifact.
Do not substitute:
1. the top-level `run_summary.run_id`, which is the session id for this fixture, or
2. `run_summary.control_plane.run_id`, which is the cards-epic run id.

The admitted resolver witness is the unique approval row with `control_plane_target_ref == <run_id>` for `approval_required_tool:write_file`, plus the validated `runs/<session_id>/run_summary.json` under the same session root.
