# AH03182026 Phase 2 Auditability Hardening Implementation Plan

Last updated: 2026-03-18
Status: Archived
Owner: Orket Core
Lane type: Archived techdebt cycle

Archive note:
1. Completed and archived on 2026-03-18.
2. Closeout authority: [docs/projects/archive/techdebt/AH03182026/Closeout.md](docs/projects/archive/techdebt/AH03182026/Closeout.md)

Requirements authority:

1. [docs/projects/archive/techdebt/AH03182026/01-REQUIREMENTS.md](docs/projects/archive/techdebt/AH03182026/01-REQUIREMENTS.md)
2. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md)

## Goal

Implement Phase 2 from the future game plan as a bounded auditability lane.

This plan makes three explicit choices:

1. freeze the Minimum Auditable Record first so scripts do not invent competing audit definitions
2. prefer auditing existing cards and ODR artifacts over adding new runtime surfaces
3. keep stability claims multi-run or replay-backed only; single-run completeness is not determinism proof

## Recommended Direction

### Auditability Choice

1. Current truth to preserve:
   1. cards and explicit ODR runs already emit most of the needed evidence
   2. no single script currently decides whether that evidence is complete
2. Recommended next choice:
   1. define the MAR surface once
   2. build thin audit operators on top of current runtime artifacts
3. Not recommended:
   1. adding a second authority document for MAR outside `docs/specs/`
   2. solving Phase 2 by broad runtime re-architecture

### Stability Choice

1. Recommended:
   1. report `not_evaluable` when only one run exists
   2. require explicit compare or replay evidence for `stable`
2. Not recommended:
   1. treating artifact presence as determinism proof
   2. hiding environment blockers behind soft success states

### Replay Choice

1. Recommended:
   1. reuse persisted turn artifacts as the replay source of truth
   2. make structural verdicts authoritative
2. Not recommended:
   1. relying on advisory semantic comparison without a structural verdict
   2. replaying from reconstructed prompts when `messages.json` already exists

## Workstream 1: Freeze MAR Inventory and Output Contracts

Objective:

1. Turn the Phase 2 idea section into one active contract plus one execution lane.

Primary surfaces:

1. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md)
2. [docs/projects/future/game-plan.md](docs/projects/future/game-plan.md)
3. [docs/ROADMAP.md](docs/ROADMAP.md)
4. [docs/README.md](docs/README.md)

Actions:

1. Freeze MAR v1 evidence groups and status vocabulary.
2. Define stable default output paths for S-01, S-02, and S-03.
3. Point the future game plan and roadmap at this lane.

Acceptance:

1. Phase 2 no longer exists only as a script-idea list.
2. Repo docs point to one active Phase 2 authority path.

Proof target:

1. structural

## Workstream 2: Implement S-01 Run Completeness Audit

Objective:

1. Determine whether one completed run is MAR-complete and replay-ready.

Primary surfaces:

1. [scripts/probes/probe_support.py](scripts/probes/probe_support.py)
2. [orket/runtime/run_summary.py](orket/runtime/run_summary.py)
3. cards and ODR artifact readers needed for MAR evidence-group checks

Actions:

1. Add `scripts/audit/verify_run_completeness.py`.
2. Reuse existing helpers for:
   1. run-summary loading
   2. protocol/runtime event inspection where helpful
   3. observability tree traversal
3. Emit one machine-readable report that records:
   1. evidence groups present and missing
   2. `mar_complete`
   3. `replay_ready`
   4. `stability_status`
4. Write rerunnable JSON to:
   1. `benchmarks/results/audit/verify_run_completeness.json`

Acceptance:

1. A reviewer can tell exactly which MAR evidence is missing without opening the workspace tree manually.
2. The script refuses to treat single-run completeness as stability proof.

Proof target:

1. contract
2. integration

## Workstream 3: Implement S-02 Equivalent-Run Compare

Objective:

1. Compare two equivalent runs at the governed MAR surface and localize the first material divergence.

Primary surfaces:

1. [orket/kernel/v1/canon.py](orket/kernel/v1/canon.py)
2. [scripts/replay/replay_comparator.py](scripts/replay/replay_comparator.py)
3. authored-output and observability artifact readers

Actions:

1. Add `scripts/audit/compare_two_runs.py`.
2. Reuse existing compare helpers where they fit without widening scope to full protocol replay.
3. Normalize only the MAR surface for this lane:
   1. run summary
   2. task verdict artifacts
   3. authored outputs
   4. per-turn observability artifacts
4. Report:
   1. excluded fresh identity differences
   2. missing evidence
   3. first governed diff path for JSON artifacts
   4. stable, diverged, or blocked verdict
5. Write rerunnable JSON to:
   1. `benchmarks/results/audit/compare_two_runs.json`

Acceptance:

1. The script can explain why two equivalent runs differ without collapsing everything into a generic failure.
2. Fresh identity-only drift does not get misreported as authored-output divergence.

Proof target:

1. contract
2. integration

## Workstream 4: Implement S-03 Replay Turn

Objective:

1. Replay one preserved turn from persisted inputs and compare the replayed output to the original preserved output.

Primary surfaces:

1. [orket/orchestration/engine.py](orket/orchestration/engine.py)
2. per-turn observability artifacts under `observability/<session_id>/`
3. runtime/provider selection helpers needed for explicit replay execution

Actions:

1. Add `scripts/audit/replay_turn.py`.
2. Reuse the persisted turn loader instead of rebuilding prompt inputs from scratch.
3. Emit authoritative structural verdicts first.
4. If an advisory semantic layer is added later, keep it separately named in the payload.
5. Write rerunnable JSON to:
   1. `benchmarks/results/audit/replay_turn.json`

Acceptance:

1. Replay reports clearly distinguish `stable`, `diverged`, and `blocked`.
2. Provider or environment failure is visible as a blocker, not a silent downgrade.

Proof target:

1. contract
2. integration
3. live

## Workstream 5: Re-Prove the Phase 2 Surfaces Live

Objective:

1. Close the lane with live evidence on the actual local-model path.

Actions:

1. Run provider preflight on the selected local model.
2. Produce at least two equivalent completed cards runs in separate workspaces so authored outputs remain independently auditable for S-02.
3. Produce one ODR-enabled cards run suitable for MAR completeness validation.
4. Run S-01 on:
   1. one completed cards run
   2. one ODR-enabled cards run
5. Run S-02 on the equivalent-run pair.
6. Run S-03 on one preserved turn from the cards run.
7. Exercise one canonical end-to-end live suite that runs the provider preflight, the probe workspaces, and S-01/S-02/S-03 together.
8. Update the future game plan if the live proof narrows any Phase 2 claim.

Acceptance:

1. Phase 2 claims are backed by live evidence where live proof is required.
2. Any blocked replay or compare path is documented explicitly instead of being hand-waved into success.
3. The canonical live suite covers the exact operator chain the plan depends on, not a parallel proof path.

Proof target:

1. live
2. structural

## Execution Sequence

1. Freeze the MAR authority and output paths before writing audit logic.
2. Land S-01 first so later operators can fail closed on incomplete evidence instead of guessing.
3. Land S-02 second with fresh-identity exclusions only after S-01 proves both runs are MAR-complete.
4. Land S-03 third using persisted turn artifacts as the only replay source of truth.
5. Add targeted structural tests and one provider-backed live suite only after the three operator surfaces exist.

## Verification Plan

Structural gates:

1. targeted tests for S-01 evidence-group detection and missing-artifact reporting
2. targeted tests for S-02 compare-surface exclusions and `first_diff_path` reporting
3. targeted tests for S-03 replay-turn artifact loading and verdict output
4. `python scripts/governance/check_docs_project_hygiene.py`

Canonical live gates:

1. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --smoke-stream`
2. two equivalent cards runs on the remediated profile used for audit comparison
3. one ODR-enabled cards run that emits `odr_artifact_path`
4. `ORKET_DISABLE_SANDBOX=1 python scripts/audit/verify_run_completeness.py ...`
5. `ORKET_DISABLE_SANDBOX=1 python scripts/audit/compare_two_runs.py ...`
6. `ORKET_DISABLE_SANDBOX=1 python scripts/audit/replay_turn.py ...`
7. `ORKET_LIVE_ACCEPTANCE=1 ORKET_DISABLE_SANDBOX=1 ORKET_LLM_PROVIDER=ollama ORKET_LIVE_MODEL=qwen2.5-coder:7b python -m pytest tests/live/test_auditability_phase2_live.py -q -s`

## Blocker Handling

1. If a fresh ODR-enabled P-04 live run terminates without `odr_artifact_path` or a persisted `odr_refinement.json`, S-01 must report `mar_complete=false`.
2. Treat that condition as a runtime blocker for lane closeout, not as permission to relax MAR v1.
3. The live suite may remain green only when it asserts that the blocker is surfaced explicitly rather than silently downgraded into success.

## Stop Conditions

1. Stop and split the lane if satisfying MAR requires a broad new runtime artifact model rather than bounded additions.
2. Stop and narrow the claim truthfully if replay requires advisory semantic scoring to look green.
3. Stop if equivalent-run compare cannot avoid false drift without silently widening or changing an existing compare contract; record the blocker and decide the contract boundary explicitly.

## Completion Gate

1. The conclusive gate in [docs/projects/archive/techdebt/AH03182026/01-REQUIREMENTS.md](docs/projects/archive/techdebt/AH03182026/01-REQUIREMENTS.md) is green.
2. The roadmap points at this plan until lane closeout.
3. When the lane closes, archive the cycle under `docs/projects/archive/techdebt/AH03182026/`.

## Completion Result

The lane completion gate is green.

1. [docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md](docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md) is active, and active docs now point to archive authority instead of the former active cycle path.
2. `scripts/audit/verify_run_completeness.py`, `scripts/audit/compare_two_runs.py`, and `scripts/audit/replay_turn.py` landed with the stable default output paths required by the lane.
3. `python -m pytest tests/scripts/test_audit_phase2.py -q` passed (`8 passed`).
4. `ORKET_LIVE_ACCEPTANCE=1 ORKET_DISABLE_SANDBOX=1 ORKET_LLM_PROVIDER=ollama ORKET_LIVE_MODEL=qwen2.5-coder:7b python -m pytest tests/live/test_auditability_phase2_live.py -q -s` passed (`1 passed`) and reported `cards_mar=True`, `odr_mar=True`, `compare=stable`, and `replay=diverged`.
5. `python scripts/governance/check_docs_project_hygiene.py` passed after archive closeout.
