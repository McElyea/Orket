# Run Lifecycle Contract (v1)

Last updated: 2026-02-22
Status: Normative

## IDs
1. `run_id`: string, unique per run.
2. `turn_id`: string, unique within `run_id`.
3. `workflow_id`: string, stable for replay scope.

## State Machine
`RUN_CREATED -> TURN_STAGED -> TURN_VALIDATED -> TURN_PROMOTED -> RUN_COMPLETED`

Failure states:
1. `RUN_FAILED`
2. `TURN_REJECTED`
3. `PROMOTION_REJECTED`

## Rules
1. Turn progression is sequential per run.
2. Promotion occurs only after validation success.
3. Invalid promotion attempts are rejected and logged.
4. Crash recovery must persist last durable state.
5. Cleanup of staging artifacts is policy-controlled and auditable.
