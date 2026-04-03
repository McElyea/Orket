# TD04032026 Challenge Workflow Runtime Truth Hardening Plan

Last updated: 2026-04-03
Status: Archived
Owner: Orket Core
Lane type: Archived techdebt cycle
Archive date: 2026-04-03

## Purpose

Fix the remaining truth, proof, and generated-artifact reliability gaps exposed by the `challenge_workflow_runtime` epic so the generated challenge submission can be believed as code, not just as orchestration output.

This cycle exists because the generated `workspace/challenge_workflow_runtime_v16/agent_output/` bundle currently passes the epic workflow while still containing semantic bugs, path-fragile tests, and compile-only verifier proof.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. `docs/projects/techdebt/README.md`
6. `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
7. `model/core/epics/challenge_workflow_runtime.json`
8. `workspace/challenge_workflow_runtime_v16/runs/49042d2c/run_summary.json`
9. `workspace/challenge_workflow_runtime_v16/agent_output/verification/runtime_verification.json`
10. `workspace/challenge_workflow_runtime_v16/agent_output/main.py`
11. `workspace/challenge_workflow_runtime_v16/agent_output/challenge_runtime/planner.py`
12. `workspace/challenge_workflow_runtime_v16/agent_output/challenge_runtime/validator.py`
13. `workspace/challenge_workflow_runtime_v16/agent_output/challenge_runtime/simulator.py`
14. `workspace/challenge_workflow_runtime_v16/agent_output/challenge_runtime/reporting.py`
15. `workspace/challenge_workflow_runtime_v16/agent_output/tests/test_validator_and_planner.py`
16. `workspace/challenge_workflow_runtime_v16/agent_output/tests/test_simulator_and_resume.py`

## Current Truth

1. The generated artifact exists and is coherent as a folder layout, but it is not yet behaviorally trustworthy.
2. The generated planner reverses dependency direction and produces backward topological layers on branched graphs.
3. The generated validator reports `unknown_dependency` and then still recurses through the missing node, causing a `KeyError` instead of a truthful validation result.
4. The generated simulator ignores dependency gating, `max_concurrency`, and `duration`, and it always reports `completed` even when prerequisite failures should block or fail the run.
5. The generated reporting module is import-broken and overclaims ownership of the summary contract.
6. The generated tests are not truthful proof:
   1. they are not importable from repo root or workspace parent
   2. several tests pass JSON strings where the implementation expects file paths
   3. several tests use path assumptions that only work from one working directory
   4. one test calls `load_checkpoint()` without importing it
7. The generated no-argument proof run is path-fragile:
   1. it works from the directory above `agent_output`
   2. it fails from inside `agent_output`
8. The generated verifier artifact currently records compile-only proof while claiming success.
9. The challenge epic and verifier path therefore still allow false-green outcomes for generated challenge code.

## Scope

In scope:
1. planner correctness for dependency direction and topological layer ordering
2. validator failure-safe handling for unknown dependencies and other declared validation errors
3. simulator dependency gating, terminal-state truth, and bounded execution semantics
4. checkpoint/resume truth if touched by simulator corrections
5. removal or repair of the broken reporting module
6. truthful path handling for the generated entrypoint and generated tests
7. upgrade of generated verification from compile-only proof to behavioral commands
8. repo-level generator, contract, and verifier changes required so fresh challenge runs cannot reproduce the same false-green surface
9. fresh rerun of the challenge epic after the fixes

Out of scope:
1. turning the generated challenge package into a production-grade reusable runtime
2. adding broad new workflow features unrelated to the exposed blocker set
3. relaxing validation or verifier gates to preserve a green status
4. using workspace-only manual edits as the final fix without updating the generator/runtime surfaces that produced the artifact

## Success Criteria

1. A fresh generated challenge artifact produces correct topological layers for linear and branched workflows.
2. Unknown dependencies yield truthful validation errors without crashing.
3. The simulator does not run downstream tasks before prerequisites succeed.
4. The simulator reports truthful terminal states instead of always returning `completed`.
5. Generated tests are importable and pass from the admitted operator surface defined in the Verification Plan.
6. The generated no-argument proof run uses stable path resolution instead of depending on one specific working directory.
7. The generated verifier artifact records behavioral proof commands, not compile-only proof alone.
8. A fresh live run of `python main.py --epic challenge_workflow_runtime` completes and the generated artifact's own proof surface is green under the upgraded verifier.
9. The final proof packet makes any remaining limitation explicit instead of implying stronger truth than the code actually supports.

## Execution Order

1. `TD-1` reproduce the generated-artifact failures in repo-backed proof
2. `TD-2` fix path/import truth for the generated package and tests
3. `TD-3` fix planner and validator correctness
4. `TD-4` fix simulator and checkpoint/resume truth
5. `TD-5` remove or repair reporting and summary-contract drift
6. `TD-6` upgrade verifier and challenge-epic proof contracts
7. `TD-7` rerun the challenge epic and evaluate closeout readiness

## Work Items

### TD-1: Reproduce The Artifact Failures Truthfully

Problem:
1. The current blocker set is known from one generated workspace, but the repo still needs hard proof that the failures are real and generator-relevant.

Implementation:
1. Add or update repo-backed tests that reproduce:
   1. reversed planner layering
   2. validator crash on unknown dependency
   3. simulator false completion after prerequisite failure
   4. reporting import failure
   5. generated-test import/path fragility
   6. compile-only verifier insufficiency
2. Keep the reproduction surfaces as small and deterministic as possible.
3. Record the admitted working-directory surfaces for the generated entrypoint and generated tests before changing them.

Acceptance:
1. Each claimed artifact defect has a named reproduction path in repo-backed proof.
2. No failure class remains based only on narrative inspection.
3. The reproduction surfaces are captured as durable repo-backed fixtures/tests rather than one-time local confirmations.

Proof target:
1. contract test
2. integration test

### TD-2: Normalize Generated Package Paths And Imports

Problem:
1. The generated bundle currently depends on one narrow working directory and one narrow import context.

Implementation:
1. Make the generated entrypoint resolve fixture and artifact paths relative to its own file location or another explicit package-root rule.
2. Make generated tests importable from the admitted operator surface without requiring ad hoc `sys.path` hacking by the user.
3. Replace hardcoded `agent_output/...` assumptions where they are not operator-truthful.
4. Use the exact admitted operator surface defined in the Verification Plan and do not allow additional implicit proof surfaces.
5. If the truthful admitted operator surface is still intentionally narrow, state it explicitly in the generated docs and verifier commands.

Acceptance:
1. The generated entrypoint no longer fails merely because it is launched from a different reasonable working directory.
2. The generated tests are importable and runnable from the admitted operator surface defined in the Verification Plan.

Proof target:
1. integration test

### TD-3: Repair Planner And Validator Semantics

Problem:
1. The planner and validator are mechanically present but logically wrong for core challenge requirements.

Implementation:
1. Correct planner edge direction so `in_degree` tracks dependents rather than prerequisites.
2. Ensure topological layer emission remains stable for deterministic inputs.
3. Make unknown dependencies report validation errors without crashing recursion.
4. Preserve duplicate-id, cycle, negative-duration, negative-retries, and empty-outcomes validation.

Acceptance:
1. Linear and branched workflows plan in the correct order.
2. Validation returns structured errors for unknown dependencies and cycles without raising an unhandled exception.

Proof target:
1. contract test
2. integration test

### TD-4: Repair Simulator And Checkpoint Truth

Problem:
1. The simulator currently fabricates success and ignores workflow semantics that the challenge claims to implement.

Implementation:
1. Make execution honor prerequisite completion before running dependent tasks.
2. Define truthful terminal states for:
   1. completed
   2. failed
   3. blocked
3. Respect `retries` when determining final outcome.
4. Before TD-4 closeout, make one explicit contract decision for `max_concurrency` and `duration`:
   1. implement them truthfully, or
   2. narrow the generated contract so they are no longer claimed
5. Record that decision in the generated docs, tests, and verifier expectations in the same change.
6. Keep checkpoint/resume aligned with the final simulator contract.

Acceptance:
1. A prerequisite failure prevents downstream execution unless the public contract explicitly says otherwise.
2. Terminal states reflect observed execution truth instead of defaulting to `completed`.
3. Resume behavior does not contradict the final simulator contract.
4. The `max_concurrency`/`duration` contract decision is explicit and locked before TD-4 is marked complete.

Proof target:
1. contract test
2. integration test

### TD-5: Remove Or Repair Reporting Drift

Problem:
1. The generated reporting module is broken and currently misstates summary-contract ownership.

Implementation:
1. Either repair `reporting.py` into a real import-safe summary helper or remove it from the generated package.
2. Keep the summary contract defined in one place only.
3. Align generated docs with the final implementation truth.

Acceptance:
1. No generated module claims ownership of a summary contract it cannot actually serve.
2. Importing the reporting surface does not fail.

Proof target:
1. contract test
2. integration test

### TD-6: Upgrade Verifier And Challenge Proof Contract

Problem:
1. Compile-only verification currently allows the generated challenge artifact to claim success while behavioral proof is still red.

Implementation:
1. Upgrade the challenge verifier contract so the generated artifact must run behavioral proof commands.
2. Prefer commands that exercise the generated package directly, for example:
   1. no-argument proof run
   2. generated test suite from the admitted operator surface
3. Keep the verifier artifact explicit about which commands actually ran.
4. Require the verifier artifact to record, for each executed proof command:
   1. command text
   2. working directory
   3. exit code
   4. pass/fail outcome
5. Do not mark the challenge green on compile-only proof for this lane.
6. Do not allow a summarized success artifact to replace per-command truth.
7. Update the challenge epic or runtime profile if required so the stronger verifier is part of the default proof path.

Acceptance:
1. `runtime_verification.json` records behavioral commands, not compile-only proof alone.
2. `runtime_verification.json` records command text, working directory, exit code, and pass/fail outcome per executed proof command.
3. A green verifier artifact means the generated package actually ran its admitted proof surface.

Proof target:
1. integration test
2. end-to-end

### TD-7: Re-Run The Challenge Epic And Evaluate Closeout

Problem:
1. Structural fixes alone are not enough if a fresh generated challenge artifact still comes out semantically false.

Implementation:
1. Run a fresh challenge epic in a clean workspace with sandbox disabled unless a real sandbox path is explicitly required.
2. Inspect the new generated artifact directly.
3. Re-run the generated proof commands from the admitted operator surface.
4. Keep the closeout truthful if any limitation remains.

Acceptance:
1. A fresh generated artifact matches the corrected planner, validator, simulator, reporting, and verifier contracts.
2. The verifier artifact is behaviorally meaningful.
3. The lane can be archived only after a fresh rerun confirms the fixes.

Proof target:
1. live
2. integration test
3. end-to-end

## Verification Plan

### Admitted Operator Surface

For this cycle, the generated challenge package is admitted only on these operator surfaces:
1. workspace parent cwd `<workspace_root>` with `python agent_output/main.py`
2. package root cwd `<workspace_root>/agent_output` with `python -m pytest -q tests`
3. no other cwd or command form counts as canonical generated-package proof unless this plan is updated in the same change

Repo-root pytest collection of the generated package does not count as canonical generated-package proof for this cycle unless packaging/import contract changes explicitly admit it.

Named hardening checks for this cycle must include:
1. targeted repo tests for planner, validator, simulator, reporting, generated-path handling, and verifier policy
2. `python scripts/governance/check_docs_project_hygiene.py`

Canonical live rerun path:
1. `ORKET_DISABLE_SANDBOX=1 python main.py --epic challenge_workflow_runtime --workspace <workspace_root> --build-id <build_id>`

Generated artifact proof after rerun:
1. from `<workspace_root>`, run `python agent_output/main.py`
2. from `<workspace_root>/agent_output`, run `python -m pytest -q tests`
3. inspect the generated `runtime_verification.json` and confirm those behavioral commands were executed
4. confirm the verifier artifact records command text, working directory, exit code, and pass/fail outcome for each executed proof command

## Archive Destination

On truthful closeout, archive this cycle to:
1. `docs/projects/archive/techdebt/TD04032026/`

## Stop Conditions

1. Stop when a fresh generated challenge artifact is behaviorally truthful and the upgraded verifier records real proof.
2. Stop early and report the blocker if the generated challenge contract itself is internally contradictory and needs a separate requirements rewrite instead of bounded hardening.
3. Do not close the lane on compile-only proof, code inspection alone, or a workspace-only hand patch.

## Closeout Status

1. Closed on 2026-04-03 after a fresh rerun at `workspace/challenge_workflow_runtime_td04032026_rerun34/` completed all twelve issues with run id `ada1f867`.
2. The admitted generated-package proof surfaces both passed on the fresh artifact:
   1. `python agent_output/main.py` from `workspace/challenge_workflow_runtime_td04032026_rerun34/`
   2. `python -m pytest -q tests` from `workspace/challenge_workflow_runtime_td04032026_rerun34/agent_output`
3. The generated verifier artifact now records behavioral command truth for `CWR-12` at `workspace/challenge_workflow_runtime_td04032026_rerun34/agent_output/verification/runtime_verification.json`.
4. Repo-side hardening proof for the generator contracts passed before the closeout rerun:
   1. `python -m pytest -q tests/platform/test_challenge_workflow_runtime_assets.py`
   2. `python -m pytest -q tests/application/test_runtime_verifier_service.py -k "issue_scoped_behavioral_commands or nested_list_json_assertions"`

## Working Status

1. `TD-1` completed
2. `TD-2` completed
3. `TD-3` completed
4. `TD-4` completed
5. `TD-5` completed
6. `TD-6` completed
7. `TD-7` completed
