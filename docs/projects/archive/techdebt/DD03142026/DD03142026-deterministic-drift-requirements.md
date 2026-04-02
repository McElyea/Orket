# DD03142026 Deterministic Drift Requirements

Last updated: 2026-03-14
Status: Archived (requirements satisfied)
Owner: Orket Core

## Purpose

Define the bounded remediation contract for the remaining live deterministic-drift gap in runtime-stability Claim E.

This cycle exists to close one truth gap only:
equivalent fresh live runs still drift under the currently intended compare contract.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
6. `docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md`
7. `docs/projects/archive/runtime-stability-closeout/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`
8. `docs/projects/archive/techdebt/DD03142026/RUNTIME-STABILITY-LIVE-COMPARE-HARDENING-PLAN.md`
9. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13.json`
10. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13/claim_e_compare.json`
11. `benchmarks/published/General/live_runtime_stability_proof_qwen2_5_coder_7b_2026-03-13/claim_e_operator_surface_diff_summary.json`

## Current Truth

1. The published runtime-stability proof is `proof_type=live`, `observed_path=primary`, and `observed_result=partial success`.
2. Published Claim A succeeded on live acceptance with run id `17d0dacd`.
3. Published Claim D succeeded on replay against that fresh live run with `compatibility_validation.status=ok`.
4. Published Claim G succeeded on the protocol-governed live path with manifest-ready tool data.
5. Published Claim E failed strict compare on equivalent fresh append-only live runs `6b3a2424` and `8faad44b`.
6. The current published Claim E diff is not only volatile run-noise:
   1. `agent_output/requirements.txt` drifted
   2. `agent_output/design.txt` drifted
   3. `agent_output/main.py` drifted
7. The published diff classifier reports `primary_layer=artifact_formatting_drift`, but the changed paths are operator-visible outputs, so Orket cannot truthfully dismiss them as harmless formatting noise without narrowing the compare contract in the same change.

## Closeout Result

Resolved on 2026-03-14.

1. Fresh live closure runs `66a2e31c`, `2855ce28`, and `8a1e9bb3` all completed successfully on the canonical live path.
2. Authored operator outputs converged across those three runs under strict compare.
3. The final governing compare contract now lives in `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` and the delta record `docs/architecture/CONTRACT_DELTA_CLAIM_E_COMPARE_SURFACE_2026-03-14.md`.
4. Final strict-compare scope:
   1. in scope: authored workspace outputs and stable scaffold files materialized for operator inspection
   2. excluded support artifacts: `agent_output/observability/runtime_events.jsonl`, `agent_output/verification/runtime_verification.json`, and interpreter cache artifacts matching `agent_output/**/__pycache__/*.pyc`
   3. fresh run identity such as `session_id` is outside deterministic-match state when all governed replay state and in-scope artifacts are otherwise equal
5. Published closure evidence lives under `benchmarks/published/General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14/` with the summary artifact `benchmarks/published/General/live_runtime_stability_claim_e_closure_qwen2_5_coder_7b_2026-03-14.json`.

## Problem Statement

What was wrong:
1. Deterministic drift existed across equivalent fresh runs.
2. Orket already has live proof that the main acceptance and replay paths work, but it does not yet have live proof that equivalent fresh runs converge under the intended compare criteria.

## Scope

In scope:
1. Runtime, prompt, adapter, serialization, or ordering behavior that can cause fresh live runs to diverge at the claimed deterministic operator surface.
2. Compare-contract narrowing if live proof shows the current claim is too broad.
3. Targeted structural tests for changed comparator or runtime behavior.
4. Live rerun proof and published artifact cleanup required to make the resolution obvious from the artifacts.

Out of scope:
1. Broad runtime redesign unrelated to Claim E.
2. Reclassifying operator-visible output drift as acceptable noise without a contract change.
3. New benchmark lanes that duplicate the existing runtime-stability proof packet.

## Equivalent Fresh Run Definition

For this cycle, equivalent fresh runs means:
1. same resolved repository commit SHA and a clean working tree for the closure run state
2. same resolved provider/model identity, including any immutable model digest or equivalent provider identity when available
3. same runtime contract and policy versions
4. same inference parameters and runtime settings that can affect output shape, token selection, serialization, or ordering
5. same prompt/template contract version or digest
6. same task input and orchestration path
7. same comparator implementation and compare-script version
8. same compare mode
9. same environment values that can affect ordering, locale, clock-derived formatting, path normalization, or serialization
10. fresh workspace/run roots with append-only ledger evidence

If any of the above differs, the runs are not equivalent for deterministic-claim purposes.

## Resolution Requirements

1. The cycle must truthfully resolve Claim E in one of two ways:
   1. remove the live drift so equivalent fresh runs match under the intended compare contract, or
   2. narrow the compare/spec claim so Orket stops claiming determinism beyond what live evidence supports.
2. If the chosen resolution is a runtime fix, the changed behavior must be attributable to a specific fix class:
   1. runtime
   2. prompt
   3. adapter
   4. serialization
   5. ordering
3. Each iteration must record exactly which causal change was attempted and must not describe a bundle of unrelated changes as a single causal change.
4. Each iteration may claim at most one causal basis for closure evidence.
5. Multi-class exploratory changes are allowed during investigation, but they must not be presented as conclusive closure evidence.
6. The final closure iteration must identify either:
   1. one causal fix class, when closure is achieved by runtime or comparator behavior change, or
   2. the specific compare-contract narrowing or scope delta, when closure is achieved by claim narrowing.
7. Allowed causal bases for this cycle are:
   1. runtime
   2. prompt
   3. adapter
   4. serialization
   5. ordering
   6. compare-contract narrowing or scope delta
8. Equivalent fresh live runs must no longer drift at any path that remains inside the final claimed deterministic operator surface.
9. Closure compare evidence must record the exact strict-compare output and show all of the following:
   1. compare command returncode `0`
   2. `deterministic_match=true` or the equivalent positive match field
   3. a positive compare status when the comparator emits an explicit status field
   4. no changed paths remain inside the final claimed deterministic operator surface
10. `python scripts/protocol/run_protocol_replay_compare.py --strict` must return a positive deterministic match under the final governing contract used for closure for the closure evidence set.
11. Acceptance and replay proof that already passed must remain green after the drift fix or contract narrowing.
12. Hardening regression checks must be enumerated in the active implementation plan or active evidence record by exact test path, script, or command.
13. No new regression may appear in those named replay/compare hardening checks for the touched surface.
14. The final published package must make the resolution legible from artifacts alone:
   1. what was wrong
   2. what changed
   3. what the new evidence shows
   4. what remains
15. If anything remains open, it must be explicit and artifact-backed.
16. Post-processing that edits published proof artifacts to hide drift without changing runtime or compare-contract truth is not an acceptable fix.

## Compare-Contract Requirements

1. Operator-visible output files stay in compare scope unless a governing contract/spec is updated in the same change.
2. Volatile artifacts may be excluded only when the governing contract explicitly excludes them.
3. If serialization or ordering is the fix, the canonical serializer or canonical ordering rule must be implemented in runtime or comparator code and covered by targeted tests.
4. If prompt shaping is the fix, the prompt/input contract that removed the drift must be identified and preserved by proof artifacts.
5. If adapter behavior is the fix, the adapter normalization must preserve runtime truth and avoid provider-specific hidden fallbacks.
6. If the deterministic operator surface is narrowed, the final package must include an explicit before/after scope statement identifying:
   1. which paths or artifact classes were removed from compare scope
   2. the governing spec or requirements change that authorizes the removal
   3. why the removed paths are no longer operator-visible under the revised contract

## Published Resolution Package Requirements

1. The final closure package must be published under one canonical published root.
2. The final closure package must include at minimum:
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
3. The package must allow a reviewer to determine the resolution without consulting unpublished workspace files or commit discussion.

## Conclusive Gate

The cycle is conclusive only when all of the following are true:
1. equivalent fresh runs no longer drift at any path that remains inside the final claimed deterministic operator surface
2. closure proof includes either:
   1. three fresh equivalent runs with strict compare match for all pairwise comparisons in the closure set, or
   2. two strict-compare pairs with no shared run ids, executed in the same final repo state, both returning a positive deterministic match
3. a single matching pair is not sufficient closure evidence for this cycle
4. compare returns a positive deterministic match under the final governing contract used for closure
5. acceptance and replay still pass
6. no new regression appears in the named hardening checks
7. the published package is clean enough that the resolution is obvious from the artifacts, not from explanation around them

## Iteration Reporting Contract

Each implementation iteration must update the active evidence record using these headings:
1. What was wrong
2. What changed
3. What the new evidence shows
4. What remains

For `What changed`, name the specific runtime, prompt, adapter, serialization, ordering, or compare-contract narrowing change.

## Residual Truth Rule

If the cycle ends with a narrowed contract instead of a runtime fix:
1. update the governing spec or requirement text in the same change
2. update the published proof package to show the narrowed contract plainly
3. state that the previous broader deterministic claim was not supported by live evidence
