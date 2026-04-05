# TD04032026B Challenge Workflow Runtime Semantic Truth Plan

Last updated: 2026-04-03
Status: Archived
Owner: Orket Core
Lane type: Archived techdebt cycle
Archive date: 2026-04-03

## Why Reopened

Archived cycle `TD04032026` materially improved the `challenge_workflow_runtime` proof surface, but it left unresolved truth gaps that were too important to leave under an archived "hardening" closeout:

1. `CWR-07` still required a corrective reprompt for tool-call formatting during rerun34.
2. The proof payload reported `dependency_cycle: true` without an explicit policy verdict, which left room for a false-green interpretation.
3. Checkpoint/resume proof covered only the happy path, not corruption handling or double-resume idempotence.
4. Invocation proof covered only one direct `main.py` path.
5. Runtime verifier stdout-contract failures were still collapsed into generic `command_failed` outcomes.

This lane is not a claim that the challenge runtime becomes globally "runtime hardened." It is a scoped truth-surface follow-up for the concrete gaps above.

## Scope

1. tighten the local qwen tool-call path so common prose-prefixed output fails closed earlier instead of depending on corrective repair
2. make the challenge proof JSON state cycle rejection policy explicitly
3. require checkpoint corruption and double-resume idempotence proof in the generated test surface
4. require both workspace-root and `agent_output` entrypoint proof plus supported module/CLI invocation proof
5. split runtime verifier stdout-contract failures into stable failure classes
6. rerun the epic live if feasible and record whether `CWR-07` still needs corrective reprompt

## Completion Gate

1. Local prompt profiles and repo tests prove the qwen tool-call path carries explicit intro denylist coverage into validator enforcement.
2. The `challenge_workflow_runtime` contract and repo-backed asset tests require explicit cycle rejection semantics in proof JSON.
3. The `challenge_workflow_runtime` contract and repo-backed asset tests require checkpoint corruption and double-resume proof.
4. The final verifier command set requires `python main.py` from inside `agent_output`, `python agent_output/main.py` from the workspace root, and `python -m challenge_runtime.cli validate challenge_inputs/workflow_valid.json`.
5. Runtime verifier tests prove stdout JSON parse failures and stdout assertion failures are classified distinctly.
6. A fresh live rerun either satisfies the tightened proof surface without a corrective reprompt on `CWR-07`, or the exact blocker remains recorded truthfully here and in the rerun evidence.

## Closeout Status

Observed on 2026-04-03:

1. Repo-side authority hardening is complete for this pass:
   - qwen local prompt profiles now carry explicit intro denylist coverage
   - legacy tool-call prompts and validator rules now reject fenced JSON explicitly
   - runtime verifier stdout-contract failures now classify parse vs assertion failures distinctly
   - the challenge epic contract now requires explicit cycle-rejection semantics, checkpoint corruption proof, double-resume proof, and broader invocation-shape proof
2. Earlier fresh rerun `workspace/challenge_workflow_runtime_td04032026b_rerun01/` with run id `4964d685` still reached `CWR-07` and required a corrective reprompt:
   - first response failed for `local_prompt_anti_meta_contract_not_met` plus `consistency_scope_contract_not_met`
   - repaired response then failed `artifact_semantic_contract_not_met_after_reprompt` because `self.terminal_state = 'blocked'` was still missing
3. Earlier fresh rerun `workspace/challenge_workflow_runtime_td04032026b_rerun02/` with run id `65d86fda` failed earlier at `CWR-01`:
   - the model continued emitting fenced JSON despite the tighter legacy prompt contract
   - the stricter validator now fails that path immediately under `LOCAL_PROMPT.MARKDOWN_FENCE` instead of allowing the run to drift further
4. Fresh rerun `workspace/challenge_workflow_runtime_td04032026b_rerun28/` completed with `status: done` in both recorded run summaries:
   - `workspace/challenge_workflow_runtime_td04032026b_rerun28/runs/237f997e/run_summary.json`
   - `workspace/challenge_workflow_runtime_td04032026b_rerun28/runs/85485c1e/run_summary.json`
5. The inspected completed run summary `workspace/challenge_workflow_runtime_td04032026b_rerun28/runs/85485c1e/run_summary.json` records one repair in `truthful_runtime_packet2.repair_ledger`, and it is scoped to `CWR-02` with `artifact_semantic_contract_not_met`.
6. No repair entry in rerun28 is attributed to `CWR-07`, so the specific live blocker that reopened this lane is resolved.
7. The generated verifier artifact at `workspace/challenge_workflow_runtime_td04032026b_rerun28/agent_output/verification/runtime_verification.json` records the widened proof commands required by this lane:
   - `python -m pytest -q tests`
   - `python -m challenge_runtime.cli validate challenge_inputs/workflow_valid.json`
   - `python main.py`
   - `python agent_output/main.py`
8. The admitted generated-package proof surface passed on rerun28:
   - `python -m pytest -q tests` from `workspace/challenge_workflow_runtime_td04032026b_rerun28/agent_output`
   - `python main.py` from `workspace/challenge_workflow_runtime_td04032026b_rerun28/agent_output`
   - `python agent_output/main.py` from `workspace/challenge_workflow_runtime_td04032026b_rerun28/`
   - `python -m challenge_runtime.cli validate challenge_inputs/workflow_valid.json` from `workspace/challenge_workflow_runtime_td04032026b_rerun28/agent_output`

This lane is archived because every scoped truth gap that reopened it is now covered by repo-side authority hardening plus fresh live evidence. The rerun still accepted one `CWR-02` corrective reprompt for artifact semantics, but the previously unresolved `CWR-07` corrective path, cycle-policy ambiguity, checkpoint corruption gap, invocation-surface gap, and stdout failure-class drift are all closed on the admitted proof surface.

## Source Authority

1. `docs/projects/archive/techdebt/TD04032026/Closeout.md`
2. `docs/projects/archive/techdebt/TD04032026/TD04032026-challenge-workflow-runtime-truth-hardening-plan.md`
3. `model/core/epics/challenge_workflow_runtime.json`
4. `tests/platform/test_challenge_workflow_runtime_assets.py`
5. `docs/architecture/CONTRACT_DELTA_CHALLENGE_RUNTIME_TRUTH_SURFACE_2026-04-03.md`
6. `workspace/challenge_workflow_runtime_td04032026b_rerun01/runs/4964d685/run_summary.json`
7. `workspace/challenge_workflow_runtime_td04032026b_rerun02/runs/65d86fda/run_summary.json`
8. `workspace/challenge_workflow_runtime_td04032026b_rerun28/runs/237f997e/run_summary.json`
9. `workspace/challenge_workflow_runtime_td04032026b_rerun28/runs/85485c1e/run_summary.json`
10. `workspace/challenge_workflow_runtime_td04032026b_rerun28/agent_output/verification/runtime_verification.json`

## Working Status

1. scoped local prompt fail-closed hardening completed
2. explicit cycle-policy proof completed
3. checkpoint corruption and double-resume proof completed
4. widened invocation-shape proof completed
5. runtime verifier stdout failure classification stabilization completed
6. fresh live rerun proof completed
