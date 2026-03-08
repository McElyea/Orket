# Core Pillars Bucket D Failure Lessons Requirements

Date: 2026-02-24  
Status: active  
Source: extracted from `docs/projects/ideas/Ideas.md` (chatter removed)

## Objective
Capture and reuse verification-failure lessons to reduce repeat failures without changing transaction authority.

## Principle
Memory is advisory, never authoritative.

Memory may:
1. warn
2. suggest preflight checks
3. suggest verify profile usage
4. suggest guardrails

Memory must not:
1. expand scope
2. bypass write barriers
3. skip verification
4. prevent rollback
5. mutate code automatically in v1

## Storage Model
1. Default local path:
- `.orket/memory/failure_lessons.jsonl`

2. Optional future storage:
- `.orket/memory/orket.sqlite` (same schema semantics)

3. Privacy:
- local-only records
- cap output tails (line and bytes caps)
- no full file snapshots by default

## Failure Lesson Record (v1 Canonical Fields)
Each verification failure event records one lesson with:
1. metadata:
- `schema_version`
- `id`
- `created_at`

2. command context:
- command name
- instruction/args
- scope
- verify profile

3. repo context:
- pre-run head
- post-revert head
- dirty-state indicator
- optional root fingerprint

4. plan context:
- touch set
- touch-set count

5. verify context:
- verify profile and commands
- failed command
- exit code
- output tail
- duration (optional)

6. classification:
- tags
- confidence
- signals (regex/model source)

7. advice:
- title
- summary
- suggested actions
- preflight checks

## Capture Rules
Record lessons when:
1. `E_VERIFY_FAILED_REVERTED`
2. `E_DRAFT_FAILURE`

Do not record lessons for:
1. user-cancel events
2. empty touch set
3. unsupported project style
4. out-of-scope write-block policy events

## Classification Rules (v1 Deterministic)
1. classifier type:
- regex + deterministic heuristics (CPU-side)

2. baseline tags:
- `missing_env_var`
- `missing_dependency`
- `type_error`
- `lint_error`
- `test_assertion_failed`
- `build_config_error`
- `port_in_use`
- `db_connection_failed`

3. optional v1.5:
- local model-assisted tag proposal allowed
- deterministic regex tags win conflicts
- model-only tags cannot block execution

## Retrieval and Warning Rules
1. retrieval timing:
- after planning and before snapshot

2. query inputs:
- command name
- scope
- touch set (top-N)
- verify profile

3. deterministic scoring signals:
- same command
- scope overlap
- touch-set intersection
- same failed verify command
- tag relevance
- recency decay

4. output behavior:
- print top-K relevant lessons as warnings
- warnings remain advisory unless strict-preflight mode is enabled

## Preflight Checks (Advisory by Default)
Supported v1 preflight check types:
1. `env_var_present`
2. `command_exists`
3. `file_exists`

Behavior:
1. preflight failures warn and continue by default
2. optional strict mode may halt

## Acceptance Tests
1. D1 record-on-fail:
- verify fail + revert creates lesson record with expected fields

2. D2 surface-before-rerun:
- relevant warning appears before execution on subsequent run

3. D3 advisory-only:
- memory warning does not change transaction safety behavior

4. D4 no-scope-expansion:
- lessons never permit writes outside scope

## Non-Goals (v1)
1. conversational companion memory
2. cross-machine sync
3. remote telemetry memory store
4. cryptographic attestations
5. global replay ledger enforcement
6. autonomous auto-fix from memory
