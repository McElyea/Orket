# DD03142026 Deterministic Drift Remediation Plan

Last updated: 2026-03-14
Status: Active
Owner: Orket Core
Lane type: Active techdebt cycle

## Purpose

Drive Claim E from live red to truthful closure without broadening scope beyond deterministic drift across equivalent fresh runs under the final governing contract used for closure.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/projects/techdebt/DD03142026-deterministic-drift-requirements.md`
6. `docs/projects/archive/runtime-stability-closeout/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`
7. `docs/projects/future/RUNTIME-STABILITY-LIVE-COMPARE-HARDENING-PLAN.md`
8. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13.json`
9. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13/claim_e_compare.json`
10. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13/claim_e_operator_surface_diff_summary.json`

## Current Truth

1. The active unresolved proof gap is published Claim E only.
2. Fresh live runs `6b3a2424` and `8faad44b` failed strict compare with `deterministic_match=false`.
3. The currently observed operator-surface drift is:
   1. `agent_output/requirements.txt`
   2. `agent_output/design.txt`
   3. `agent_output/main.py`
4. The currently observed volatile drift is:
   1. `agent_output/observability/runtime_events.jsonl`
   2. `agent_output/verification/runtime_verification.json`
5. Acceptance, replay, fail-closed boundary proof, and governed-runtime manifest proof already passed in the published packet.
6. The cycle therefore must not reopen closed claims unless the deterministic-drift fix regresses them.

## Scope

In scope:
1. reproduce the current Claim E drift on the canonical live path
2. isolate the smallest truthful causal basis
3. implement the smallest fix that removes the drift or narrows the compare claim truthfully
4. prove that acceptance and replay remain green
5. publish a clean evidence packet that shows the resolution directly

Out of scope:
1. sweeping runtime cleanup unrelated to Claim E
2. retrofitting unrelated historical proof packets
3. changing compare semantics and runtime behavior in the same iteration unless a single bounded root cause requires both

## Success Criteria

1. Equivalent fresh runs no longer drift at any path that remains inside the final claimed deterministic operator surface.
2. Closure proof satisfies the anti-flake rule from `DD03142026-deterministic-drift-requirements.md`.
3. `run_protocol_replay_compare.py --strict` returns success for every required closure comparison under the final governing contract used for closure.
4. Acceptance and replay still pass on the fresh proof path.
5. No new regression appears in the named hardening checks for touched compare/replay/runtime surfaces.
6. The published package makes the remediation obvious without surrounding prose.

## Execution Order

1. `DD-1` baseline freeze and compare-contract governance
2. `DD-2` root-cause isolation by causal basis
3. `DD-3` bounded implementation and structural proof
4. `DD-4` live rerun and closure gate evaluation
5. `DD-5` published artifact cleanup and lane closeout decision

## Work Items

### DD-1: Freeze The Baseline And Govern Compare-Contract Changes

Problem:
1. The repo already contains live evidence of drift, but the baseline claim and compare surface must stay fixed until superseded by an explicit governed contract change recorded in the active iteration.

Implementation:
1. Treat the 2026-03-13 published Claim E packet as the baseline until a newer live packet supersedes it.
2. Preserve the current operator-surface changed-path list as the initial defect statement.
3. Record the resolved closure-run identity fields before any conclusive rerun:
   1. repository commit SHA
   2. clean working-tree confirmation
   3. resolved model identity and digest when available
   4. inference settings
   5. prompt/template contract version or digest
   6. comparator implementation identity
   7. environment values that can affect ordering or serialization
4. Confirm before each implementation attempt whether the planned causal basis is:
   1. runtime
   2. prompt
   3. adapter
   4. serialization
   5. ordering
   6. compare-contract narrowing or scope delta
5. Reject any iteration that cannot name its causal basis.

Acceptance:
1. Each attempt starts from a fixed baseline claim and a named compare contract.
2. Closure reruns pin the exact runtime identity instead of a loose model tag or informal repo state.
3. Any compare-surface change is explicit and governed rather than implied.

Proof target:
1. structural

### DD-2: Isolate One Causal Basis At A Time

Problem:
1. The current drift spans three operator-visible files, and a multi-cause patch would destroy causal clarity.

Implementation:
1. Inspect the current drift artifacts and map each changed path to the most likely causal basis.
2. Choose one causal basis per iteration.
3. Add or update targeted tests that lock the intended deterministic behavior for the touched surface.
4. Do not mix contract narrowing with unrelated runtime cleanup.
5. If an exploratory iteration touches multiple causal bases, mark it exploratory-only and keep it out of closure evidence.

Acceptance:
1. The iteration has one declared cause hypothesis and one bounded causal basis.
2. The touched surface has targeted structural proof before live rerun.
3. The final closure iteration names one causal basis.

Proof target:
1. contract test
2. integration test

### DD-3: Apply The Smallest Truthful Fix

Problem:
1. The live proof is red because the runtime currently produces drift that the compare contract still considers real.

Implementation:
1. Change only the runtime, prompt, adapter, serialization, or ordering surface that matches the active root-cause hypothesis.
2. If the truthful outcome is contract narrowing instead of runtime change:
   1. update the governing requirement or spec in the same change
   2. keep operator-visible output drift out of scope only if the new contract says so explicitly
   3. include an explicit before/after compare-scope statement naming removed paths or artifact classes and the authority change that permits the removal
3. Keep structural proof aligned with the chosen resolution path.

Acceptance:
1. The code and docs tell the same deterministic story.
2. No fix relies on editing proof artifacts after the fact.
3. Narrowing evidence includes an auditable scope delta rather than an implied shrinkage of the claim.

Proof target:
1. contract test
2. integration test

### DD-4: Re-Run Live Closure Proof

Problem:
1. Structural proof is necessary but not sufficient for a live deterministic-drift claim.

Implementation:
1. Run provider preflight on the active local provider/model.
2. Produce closure evidence using either:
   1. three fresh equivalent runs with all pairwise strict comparisons passing, or
   2. two strict-compare pairs with no shared run ids in the same final repo state, with both pairs passing
3. Record the strict-compare command outputs and return codes for every closure comparison.
4. Re-run replay against the fresh live path.
5. Re-run the named hardening checks for touched replay/compare/runtime surfaces.

Acceptance:
1. Every required closure comparison returns returncode `0` and `deterministic_match=true`.
2. No changed paths remain inside the final claimed deterministic operator surface.
3. Acceptance and replay remain green.
4. Named hardening checks remain green.

Proof target:
1. live
2. contract test
3. integration test

### DD-5: Publish A Clean Resolution Packet

Problem:
1. A fixed run is not enough if the published package still needs surrounding explanation to understand the resolution.

Implementation:
1. Refresh the published proof only after the conclusive gate is green.
2. Publish the closure package under one canonical published root.
3. Ensure the published package includes at minimum:
   1. one summary or index artifact
   2. one artifact showing the pre-resolution Claim E drift
   3. one artifact showing the post-fix or post-narrowing strict compare result
   4. rerun acceptance proof artifact or artifacts
   5. rerun replay proof artifact or artifacts
   6. environment and provenance artifact or artifacts
   7. one resolution note artifact using these headings:
      1. What was wrong
      2. What changed
      3. What the new evidence shows
      4. What remains
4. Keep the artifact set tight enough that the resolution is visible from the JSON and supporting diff artifacts.
5. If published artifacts change, update:
   1. `benchmarks/published/index.json`
   2. `benchmarks/published/README.md`

Acceptance:
1. The published packet is self-explanatory.
2. The package does not require narrative around it to prove the fix.
3. A reviewer can determine the resolution without consulting unpublished workspace files or commit discussion.

Proof target:
1. live

## Iteration Rules

1. One causal basis per iteration.
2. One canonical active plan and one active requirements doc only.
3. Update the evidence record each iteration with:
   1. What was wrong
   2. What changed
   3. What the new evidence shows
   4. What remains
4. Each iteration may claim at most one causal basis for closure evidence.
5. Multi-basis exploratory changes are allowed during investigation, but they must not be presented as conclusive closure evidence.
6. The final closure iteration must identify one causal basis.
7. For each iteration, any targeted structural tests added or updated for the touched surface must be recorded in the active evidence record as named hardening checks before closure is claimed.
8. Do not call the lane resolved on structural proof alone.
9. If a live rerun is blocked, state the blocker and stop rather than claiming conclusive closure.

## Verification Plan

Named hardening regression checks:
1. `python -m pytest tests/runtime/test_protocol_replay.py tests/interfaces/test_cli_protocol_replay.py tests/scripts/test_run_protocol_replay_compare.py -q`
2. `python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --auto-select-model --smoke-stream`
3. Iteration-specific targeted structural tests for the touched surface must be added to the active evidence record as named hardening checks before closure is claimed.

Canonical live closure path:
1. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_a`
2. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_b`
3. Optional anti-flake third-run path when using the three-run closure mode:
   1. `ORKET_LIVE_ACCEPTANCE=1 ORKET_LIVE_MODEL=qwen2.5-coder:7b ORKET_RUN_LEDGER_MODE=append_only python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s --basetemp <attempt_root>/pytest_tmp_claim_e_run_c`
4. `python scripts/protocol/run_protocol_replay_compare.py --run-a-events <run_a_events> --run-b-events <run_b_events> --run-a-artifacts <run_a_artifacts> --run-b-artifacts <run_b_artifacts> --out <compare_json> --strict`
5. Additional strict-compare invocations required by the chosen closure mode:
   1. run A vs run C
   2. run B vs run C
   3. or the second independent closure pair
6. Replay the fresh run through the canonical CLI replay surface using `python main.py protocol replay <run_id> --workspace <workspace_root>` and record the JSON stdout as the replay artifact showing `compatibility_validation.status=ok`.

Governance/doc gates:
1. `python scripts/governance/check_docs_project_hygiene.py`
2. If published artifacts change:
   1. `python scripts/governance/sync_published_index.py --write`
   2. `python scripts/governance/sync_published_index.py --check`

## Stop Conditions

1. Stop when the conclusive gate in `DD03142026-deterministic-drift-requirements.md` is green.
2. Stop early if the active hypothesis requires a repo-wide redesign instead of a bounded deterministic-drift fix; record the blocker truthfully.
3. Stop and reassess if a proposed fix reopens previously closed claims A, D, or G.

## Working Status

1. `DD-1` active
2. `DD-2` pending
3. `DD-3` pending
4. `DD-4` pending
5. `DD-5` pending
