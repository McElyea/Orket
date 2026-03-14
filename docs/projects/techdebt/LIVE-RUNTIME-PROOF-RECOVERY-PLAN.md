# Live Runtime Proof Recovery Plan

Last updated: 2026-03-13
Status: Active
Owner: Orket Core
Scope anchor: runtime-stability closeout checkpoint `b739d07` (`feat: close runtime-stability lane`)

## Purpose

Provide one durable recovery plan for proving the recently closed runtime-stability work through real runtime execution instead of structural tests alone.

This document exists so a future session can resume live proof work without reconstructing:
1. what was shipped,
2. which claims still need live confirmation,
3. which commands and evidence paths should be used,
4. which blockers are acceptable and how they must be recorded.

## Current Context

The structural closeout work already landed and is locally committed.

Closed scope covered by this recovery plan:
1. `SPC-01` v0 boundary narrowing and fail-closed boundary proof
2. `SPC-02` protocol replay CLI/operator surface
3. `SPC-05` canonical `run_summary.json` emission and replay reconstruction
4. `SPC-06` minimal tool-registry and invocation-manifest contract
5. roadmap/archive cleanup that moved runtime-stability docs under `docs/projects/archive/`

What is not yet live-proven:
1. a provider-backed or otherwise real engine run that produces a fresh protocol run directory after the closeout changes
2. operator execution of replay/compare commands against that fresh run data
3. a live fail-closed reproduction of the replay compatibility path for missing `workspace_state_snapshot`
4. live inspection of emitted invocation-manifest data from the real run artifacts/events

## Proof Rules

Use these labels in evidence and final reporting:
1. observed path: `primary`, `fallback`, `degraded`, or `blocked`
2. observed result: `success`, `failure`, `partial success`, or `environment blocker`

Do not count any step as live proof unless it executes shipped runtime code against a real filesystem workspace and writes fresh runtime artifacts or operator-visible outputs.

Pure unit/contract tests are supporting evidence only.

## Evidence Root

Use one proof id per attempt:
1. proof id format: `YYYY-MM-DD_live-proof_<suffix>`
2. canonical root: `benchmarks/results/techdebt/live_runtime_proof/<proof_id>/`

Minimum files per attempt:
1. `commands.txt`
2. `environment.json`
3. `result.json`
4. `stdout.log`
5. `stderr.log`
6. `claims.json`

Recommended subfolders:
1. `workspaces/`
2. `runs/`
3. `replay_outputs/`
4. `mutations/`

## Preconditions

Before starting:
1. record `git rev-parse HEAD`
2. record Python version and active env toggles
3. decide whether provider-backed proof is available
4. choose a clean temporary runtime workspace under the attempt root

Provider-backed proof prerequisites:
1. a reachable local/provider model
2. any required env flags for the provider path
3. confirmation that the model can execute a real Orket card run

If provider-backed proof is unavailable, continue with the provider-free runtime-harness steps and record the provider step as `blocked`.

## Claim Matrix

### Claim A: Real engine run still completes after the closeout changes

Primary path:
1. run the existing live acceptance target:
   - `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s`
2. required env:
   - `ORKET_LIVE_ACCEPTANCE=1`
   - `ORKET_LIVE_MODEL=<model>`

Fallback path when provider is unavailable:
1. run the provider-free runtime-harness target:
   - `python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard -q -s`
2. treat this as live proof of the real engine/filesystem path, but not of provider-backed behavior

Success criteria:
1. all issues reach `DONE`
2. fresh files exist:
   - `agent_output/requirements.txt`
   - `agent_output/design.txt`
   - `agent_output/main.py`
   - `agent_output/verification/runtime_verification.json`
3. fresh checkpoint artifacts exist under `observability/`

Evidence to copy:
1. printed issue statuses
2. produced workspace files
3. runtime verification payload
4. checkpoint artifact sample

### Claim B: Boundary violations still fail closed in a real runtime run

Execution path:
1. run the real engine boundary flows:
   - `python -m pytest tests/integration/test_engine_boundaries.py::test_illegal_state_transition_blocked -q -s`
   - `python -m pytest tests/integration/test_engine_boundaries.py::test_path_traversal_blocked -q -s`

Why these count:
1. they execute `OrchestrationEngine.run_card(...)`
2. they write real policy-violation artifacts in a real temp workspace
3. they do not rely on mocked dispatcher/runtime internals

Success criteria:
1. run aborts fail closed
2. issue status ends `BLOCKED`
3. `agent_output/policy_violation_<issue>.json` exists with the expected violation type

Evidence to copy:
1. violation artifact JSON
2. final issue status
3. terminal output showing the raised failure path

### Claim C: A fresh real run emits canonical `run_summary.json`

Primary path:
1. use the run produced by Claim A
2. locate the fresh run id under `<workspace>/runs/<run_id>/`
3. verify:
   - `<workspace>/runs/<run_id>/run_summary.json`

If Claim A was executed through pytest:
1. inspect the test workspace under pytest temp output
2. copy the full run directory into the proof root before cleanup, or rerun under a controlled proof workspace

Success criteria:
1. `run_summary.json` exists in the run root
2. its contents match the finalized run state
3. it contains stable status, counts, and contract hashes rather than a degraded fallback error payload

Evidence to copy:
1. `run_summary.json`
2. sibling `events.log`
3. sibling `receipts.log` if present

### Claim D: Operator replay still works against the fresh run

Execution path:
1. run the operator CLI replay command against the real run:
   - `python main.py protocol replay <run_id> --workspace <proof_workspace>`

Success criteria:
1. command exits `0`
2. printed replay JSON resolves the same run identity/status as `run_summary.json`
3. no compatibility or ledger error is raised for the untouched fresh run

Evidence to copy:
1. replay JSON
2. command line used

### Claim E: Equivalent fresh runs compare cleanly at the operator surface

Execution path:
1. produce two equivalent runs using Claim A on two clean proof workspaces
2. run:
   - `python main.py protocol compare <run_a_id> --protocol-run-b <run_b_id> --workspace <proof_workspace>`
3. optionally also run:
   - `python scripts/protocol/run_protocol_replay_compare.py --run-a-events <run_a_events> --run-b-events <run_b_events> --run-a-artifacts <run_a_artifacts> --run-b-artifacts <run_b_artifacts>`

Success criteria:
1. comparison reports `deterministic_match=true`
2. no unexplained differences are present

Evidence to copy:
1. compare JSON output
2. both `run_summary.json` files

### Claim F: Missing `workspace_state_snapshot` now fails closed instead of scanning the repo

Important note:
1. `python main.py protocol replay ...` does not currently expose the strict compatibility flags needed for this proof
2. this claim therefore needs a small inline Python harness that calls `ProtocolReplayEngine.replay_from_ledger(...)` with:
   - `enforce_runtime_contract_compatibility=True`
   - `require_replay_artifact_completeness=True`

Execution path:
1. copy a real run directory from Claim A into `mutations/<run_id>-missing-workspace-snapshot/`
2. remove or blank the `workspace_state_snapshot` data from the copied `run_started` surface
3. run an inline Python harness against the mutated `events.log`

Expected outcome:
1. raise `ValueError`
2. message contains `E_REPLAY_ARTIFACTS_MISSING`
3. message names `workspace_state_snapshot.workspace_hash` and related fields
4. no repo-wide workspace scan or hang occurs

Evidence to copy:
1. mutated artifact/event input
2. exact Python harness
3. terminal output/error text

### Claim G: The minimal invocation-manifest contract is present in real run data

Execution path:
1. inspect the fresh run from Claim A
2. parse the first receipt or tool event containing `tool_invocation_manifest`
3. confirm fields:
   - `tool_name`
   - `ring`
   - `schema_version`
   - `determinism_class`
   - `capability_profile`
   - `tool_contract_version`
4. confirm richer registry metadata is absent:
   - `input_schema`
   - `output_schema`
   - `error_schema`
   - `side_effect_class`
   - `timeout`
   - `retry_policy`

Suggested command form:
1. use a short inline Python reader over `receipts.log` or `events.log`

Success criteria:
1. manifest fields match the narrowed SPC-06 contract
2. no richer registry metadata is being falsely implied in the live payload

## Execution Order

Run in this order:
1. establish proof root and environment metadata
2. Claim A
3. Claim B
4. Claim C
5. Claim D
6. Claim E
7. Claim F
8. Claim G
9. summarize all claims in `claims.json` and `result.json`

## Reporting Template

For each claim, record:
1. `claim_id`
2. `description`
3. `path`
4. `result`
5. `command`
6. `artifacts`
7. `notes`

Use this result schema:

```json
{
  "claim_id": "claim-a",
  "description": "real engine run completes",
  "path": "primary",
  "result": "success",
  "command": "python -m pytest tests/live/test_system_acceptance_pipeline.py::test_system_acceptance_role_pipeline_with_guard_live -q -s",
  "artifacts": [
    "workspaces/claim-a/agent_output/main.py",
    "workspaces/claim-a/observability/.../checkpoint.json"
  ],
  "notes": "provider-backed live run completed"
}
```

## Acceptable Blockers

Record as `environment blocker` only when one of these is true:
1. no reachable live model/provider is available for Claim A primary path
2. temp workspace cleanup destroys the run before it can be copied and the session cannot be rerun immediately
3. an operator entrypoint required for the claim does not expose the necessary strict flags and must be replaced by an inline runtime harness

Do not record a blocker when:
1. a fallback real runtime path exists and was not attempted
2. the claim can be proven with the existing local engine plus real filesystem execution

## Exit Condition

This live-proof effort is complete when:
1. every claim above is either `success` or an explicitly justified `environment blocker`
2. at least one fresh real run directory has been captured under the proof root
3. replay output, run summary output, and invocation-manifest evidence are copied into the proof root
4. the final result clearly separates:
   - provider-backed live proof
   - provider-free real runtime proof
   - blocked claims
