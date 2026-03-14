# DD03142026 Deterministic Drift Remediation Plan

Last updated: 2026-03-14
Status: Archived
Owner: Orket Core
Lane type: Archived techdebt cycle

## Purpose

Drive Claim E from live red to truthful closure without broadening scope beyond deterministic drift across equivalent fresh runs under the final governing contract used for closure.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/projects/archive/techdebt/DD03142026/DD03142026-deterministic-drift-requirements.md`
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

## Completion Result

The lane conclusive gate is green.

1. Closure mode used the three-run anti-flake path with fresh live runs `66a2e31c`, `2855ce28`, and `8a1e9bb3`.
2. Pairwise strict compare passed for all three closure pairs under the final governed compare contract.
3. Replay on run `66a2e31c` returned `status=done` and `compatibility_validation.status=ok`.
4. Named hardening checks remained green.
5. Published closure evidence lives in `benchmarks/published/General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14/` with summary artifact `benchmarks/published/General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14.json`.

## Active Evidence Record

### Iteration 2026-03-14A

What was wrong
1. Baseline inspection pinned the active repo state at commit `81e056cb00164d9bab4dc29ad91e17e39064180e` with no tracked worktree drift from `git status --porcelain=v1 --untracked-files=no`.
2. Published Claim E rerun4 evidence showed identical `messages.json` inputs for `REQ-1`, `ARC-1`, and `COD-1` across runs `6b3a2424` and `8faad44b`, but different `model_response.txt` outputs for each seat.
3. The rerun4 raw provider telemetry for `REQ-1` showed `task_class=concise_text` with a stochastic Ollama sampling bundle (`temperature=0.2`, `top_p=0.9`, `top_k=40`, `seed_policy=provider_default`) even though the turn required tool-call output.
4. Declared causal basis for this iteration: `adapter`.

What changed
1. Updated `orket/adapters/llm/local_prompting_policy.py` so any turn with non-empty `required_action_tools` resolves to `tool_call` even when `protocol_governed_enabled` is false.
2. Added `tests/adapters/test_local_prompting_policy.py::test_resolve_local_prompting_policy_uses_tool_call_bundle_when_required_tools_exist_without_protocol_governance` to lock the legacy non-governed required-tool path onto the deterministic `tool_call` sampling bundle.
3. Named hardening checks for this iteration:
   1. `python -m pytest tests/adapters/test_local_prompting_policy.py tests/application/test_turn_executor_runtime_context_bridge.py -q`

What the new evidence shows
1. Structural proof only: `python -m pytest tests/adapters/test_local_prompting_policy.py tests/application/test_turn_executor_runtime_context_bridge.py -q` passed with `11 passed in 0.43s`.
2. The touched surface now routes required-tool turns to the deterministic `tool_call` prompt profile bundle already defined in `model/core/contracts/local_prompt_profiles.json`.
3. The bounded fix matches the observed defect statement: same prompt input, different provider output caused by the runtime selecting a stochastic task class for a structured tool-call turn.

What remains
1. Live proof is still required; this iteration does not claim Claim E closure.
2. `DD-4` still needs provider preflight, fresh equivalent live reruns, strict compare success under the final contract, replay, and named hardening checks.
3. No published artifacts were updated in this iteration.
4. If fresh live reruns still drift after the task-class correction, stop and reassess rather than broadening the same fix path.

### Iteration 2026-03-14B

What was wrong
1. The first live rerun after iteration `2026-03-14A` failed at `REQ-1` with `LOCAL_PROMPT.MARKDOWN_FENCE` even though the failing turn was a legacy non-protocol required-tool path.
2. Declared causal basis for this iteration: `runtime`.

What changed
1. Updated `orket/application/workflows/turn_contract_validator.py` so the markdown-fence violation is emitted only when `protocol_governed_enabled` is true.
2. Updated `tests/application/test_turn_contract_validator.py` to keep the protocol-governed fence rejection and to prove the legacy non-protocol tool path remains allowed.
3. Named hardening checks for this iteration:
   1. `python -m pytest tests/application/test_turn_contract_validator.py -q`

What the new evidence shows
1. Structural proof only: `python -m pytest tests/application/test_turn_contract_validator.py -q` passed after the validator change.
2. The next live rerun advanced past `REQ-1`, showing the red path had moved off the legacy fence validator and onto later seats.

What remains
1. Claim E was still live-red after `REQ-1`; this iteration removed one false boundary but did not close the lane.
2. `ARC-1` still drifted because the architect prompt contract did not yet match the JSON artifact validator.

### Iteration 2026-03-14C

What was wrong
1. `ARC-1` wrote markdown-style `design.txt` content while the runtime and artifact validator required architecture-decision JSON.
2. Reviewer prompt assets also still under-described the read-path contract needed for later live seats.
3. Declared causal basis for this iteration: `prompt`.

What changed
1. Updated `orket/application/services/prompt_compiler.py` and `orket/application/services/canonical_role_templates.py` so the architect turn contract explicitly requires the architecture-decision JSON payload.
2. Updated `model/core/roles/architect.json`, `model/core/roles/code_reviewer.json`, and the live acceptance seed prompt descriptions in `tests/live/test_system_acceptance_pipeline.py` to align the shipped role assets with the governed prompt contract.
3. Added `tests/application/test_prompt_compiler.py::test_prompt_compiler_architect_requires_architecture_decision_json_artifact`.
4. Named hardening checks for this iteration:
   1. `python -m pytest tests/application/test_prompt_compiler.py tests/application/test_prompts_cli.py tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard -q`

What the new evidence shows
1. Structural proof only: the targeted prompt/compiler suite passed.
2. Fresh live rerun then progressed through `ARC-1` and `COD-1`, proving the architect seat now matched the required JSON artifact contract.
3. Reviewer still failed, so prompt strengthening alone was not the full Claim E fix.

What remains
1. `REV-1` still failed on the live path and needed a narrower causal basis than prompt wording alone.
2. Prompt-only evidence was not sufficient for closure.

### Iteration 2026-03-14D

What was wrong
1. `REV-1` still returned too few `read_file` calls even after reviewer prompt alignment.
2. Raw live output inspection showed the local provider was forcing Ollama `format=\"json\"` on legacy `tool_call` turns, constraining the provider to a single top-level JSON object and preventing the repeated tool-call blocks that reviewer needs.
3. Declared causal basis for this iteration: `adapter`.

What changed
1. Updated `orket/adapters/llm/local_model_provider.py` so `format=\"json\"` is requested only for `strict_json`, not for legacy `tool_call` turns.
2. Updated `docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md` to make the legacy multi-tool-call allowance explicit.
3. Added `tests/adapters/test_local_model_provider_telemetry.py::test_local_model_provider_ollama_legacy_tool_call_turns_do_not_request_json_format`.
4. Named hardening checks for this iteration:
   1. `python -m pytest tests/adapters/test_local_model_provider_telemetry.py tests/application/test_prompt_compiler.py tests/application/test_prompts_cli.py tests/application/test_turn_contract_validator.py tests/adapters/test_local_prompting_policy.py tests/application/test_turn_executor_runtime_context_bridge.py tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard -q`

What the new evidence shows
1. Structural proof: the targeted adapter and prompt/runtime regression suite passed with `50 passed in 10.40s`.
2. Fresh live runs `66a2e31c`, `2855ce28`, and `8a1e9bb3` all completed successfully through `REQ-1`, `ARC-1`, `COD-1`, and `REV-1`.
3. Authored operator files matched across the three live runs, leaving only runtime-generated support artifact drift and session-identity compare drift to resolve.

What remains
1. Strict compare still needed truthful closure under the final governed compare contract.
2. The remaining red surface had narrowed to compare semantics, not authored operator outputs.

### Iteration 2026-03-14E

What was wrong
1. Unfiltered strict compare on the fresh live runs still drifted only in `observability/runtime_events.jsonl`, `verification/runtime_verification.json`, interpreter cache artifacts under `__pycache__`, and state digests that changed only because `session_id` differed per fresh run.
2. Authored operator outputs and stable scaffold files were already matching, so the remaining failure was a compare-contract truth gap rather than authored-output nondeterminism.
3. Declared causal basis for this iteration: `compare-contract narrowing or scope delta`.

What changed
1. Updated `orket/runtime/protocol_replay.py` so fresh `session_id` differences do not perturb strict-compare state digests when all governed replay state otherwise matches.
2. Added `tests/runtime/test_protocol_replay.py::test_protocol_replay_engine_compare_ignores_fresh_session_identity_when_state_matches`.
3. Updated `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` and `docs/architecture/CONTRACT_DELTA_CLAIM_E_COMPARE_SURFACE_2026-03-14.md` to define the final strict compare operator surface and the excluded runtime-generated support artifacts.
4. Published the closure packet under `benchmarks/published/General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14/`.
5. Named hardening checks for this iteration:
   1. `python -m pytest tests/runtime/test_protocol_replay.py tests/scripts/test_run_protocol_replay_compare.py -q`
   2. `python -m pytest tests/runtime/test_protocol_replay.py tests/interfaces/test_cli_protocol_replay.py tests/scripts/test_run_protocol_replay_compare.py -q`
   3. `python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --auto-select-model --smoke-stream`

What the new evidence shows
1. Structural proof: `python -m pytest tests/runtime/test_protocol_replay.py tests/scripts/test_run_protocol_replay_compare.py -q` passed with `19 passed in 0.47s`.
2. Structural proof: `python -m pytest tests/runtime/test_protocol_replay.py tests/interfaces/test_cli_protocol_replay.py tests/scripts/test_run_protocol_replay_compare.py -q` passed with `29 passed in 1.06s`.
3. Live proof: provider preflight passed with `PREFLIGHT=PASS`.
4. Live proof: pairwise strict compare under the final governed scope returned `deterministic_match=true` with returncode `0` for `A/B`, `A/C`, and `B/C`.
5. Live proof: replay on run `66a2e31c` returned `status=done` with `compatibility_validation.status=ok`.
6. Governance proof: `python scripts/governance/check_docs_project_hygiene.py` passed.

What remains
1. Nothing remains open for this cycle; the lane conclusive gate is green and the cycle moved to archive.

## Working Status

1. `DD-1` completed
2. `DD-2` completed
3. `DD-3` completed
4. `DD-4` completed
5. `DD-5` completed
