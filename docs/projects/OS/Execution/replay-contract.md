# Replay Contract (v1)

Last updated: 2026-02-22
Status: Normative

## Replay Inputs
1. Run envelope identity (`run_id`, `workflow_id`, version fields).
2. Policy/model/runtime profile references.
3. Trace artifacts and validation issues.
4. Deterministic state references (snapshot/index refs).

## Match Requirements
Must match:
1. Stage order and stage outcomes.
2. Error and info codes (with pointers and stages).
3. Contract digests and schema versions.

May differ:
1. Host-local absolute paths.
2. Non-contract diagnostic text not used for policy decisions.

## Failure Codes
1. `E_REPLAY_INPUT_MISSING`
2. `E_REPLAY_VERSION_MISMATCH`
3. `E_REPLAY_EQUIVALENCE_FAILED`
