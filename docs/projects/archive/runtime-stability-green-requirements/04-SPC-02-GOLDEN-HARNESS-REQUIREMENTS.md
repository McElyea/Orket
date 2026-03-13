# SPC-02 Golden Harness Closeout Requirements

Last updated: 2026-03-13
Status: Archived
Owner: Orket Core
Parent lane: `docs/projects/archive/runtime-stability-green-requirements/02-IMPLEMENTATION-PLAN.md`
Closeout source: `docs/projects/archive/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`

Archive note: Historical requirements packet preserved after direct SPC-02 closeout completed on 2026-03-13.

## 1. Purpose

Define a bounded, truthful closeout target for the removed `golden run harness + deterministic replay + run determinism tests` item.

This packet exists because protocol replay and determinism-campaign infrastructure are shipped, but the active requirement text still promises a fixture-based `golden/<test>` operator surface that is not currently the canonical runtime interface.

## 2. Scope

In scope:
1. canonical replay and golden-harness interface decision
2. whether fixture-based golden runs remain active scope
3. exact proof needed for honest closeout
4. relationship between protocol replay, determinism campaign, and any future fixture harness

Out of scope:
1. prompt-budget closeout
2. scoreboard/dashboard work
3. replay behavior unrelated to the golden closeout claim

## 3. Current Structural Evidence

Current shipped evidence already covers:
1. protocol replay reconstruction in `orket/runtime/protocol_replay.py`
2. protocol replay CLI surface in `orket/interfaces/cli.py`
3. determinism campaign support in `orket/runtime/protocol_determinism_campaign.py`
4. replay comparison and campaign script paths in:
   1. `scripts/protocol/run_protocol_replay_compare.py`
   2. `scripts/protocol/run_protocol_determinism_campaign.py`
5. structural proof in:
   1. `tests/runtime/test_protocol_replay.py`
   2. `tests/runtime/test_protocol_determinism_campaign.py`
   3. `tests/scripts/test_run_protocol_replay_compare.py`
   4. `tests/scripts/test_run_protocol_determinism_campaign.py`
   5. `tests/reports/replay_integrity_test_report.json`

Current active requirement text still claims additional coverage for:
1. `orket run golden/<test>`
2. `orket replay golden/<test>`
3. canonical golden fixtures containing:
   1. `input.json`
   2. `expected_tool_calls.json`
   3. `expected_artifacts.json`
   4. `expected_status.json`

## 4. Closeout Requirements

### 4.1 Canonical Operator Surface Must Be Chosen

The direct implementation plan must choose one canonical closeout surface:
1. `protocol replay is canonical`
   - run-id replay and determinism campaigns become the authoritative replay surface
   - golden fixtures become optional wrappers or are removed from active requirements
2. `fixture harness is canonical`
   - a user-facing `golden/<test>` interface remains part of the closeout target
3. `dual-surface contract`
   - both surfaces remain active, with explicit separation of responsibilities

Recommended default:
1. choose `protocol replay is canonical`, and if golden fixtures remain useful, make them a thin wrapper over the shipped replay engine instead of a parallel replay stack

Acceptance:
1. one canonical operator story is selected
2. the non-canonical alternatives are either excluded or subordinated
3. the source-of-truth docs reflect the same surface

### 4.2 Fixture Contract Must Be Explicit If Fixtures Stay In Scope

If fixture-based golden runs remain in scope, the direct implementation plan must define:
1. canonical fixture storage location
2. fixture schema versioning
3. how `input.json`, `expected_tool_calls.json`, `expected_artifacts.json`, and `expected_status.json` are validated
4. how fixture staleness is handled when tool registry or runtime contract versions change

Required rule:
1. fixture metadata must record compatibility anchors such as:
   1. `tool_registry_version`
   2. `runtime_contract_hash`
   3. any other version fields needed to fail closed on stale fixtures

Acceptance:
1. fixture files are fully specified if they remain active scope
2. stale-fixture behavior is explicit and fail-closed

### 4.3 Replay/Comparison Behavior Must Stay Single-Sourced

The closeout target must not create duplicate replay engines with divergent semantics.

Required rule:
1. any future golden harness must reuse the shipped replay and comparison primitives unless an explicit replacement decision is recorded

Acceptance:
1. replay logic has one authoritative engine
2. comparison/drift behavior is defined in one canonical path

### 4.4 Proof Layer Must Match The User-Facing Surface

The eventual proof must exercise the chosen closeout surface directly, not only the lower-level engine.

Required rule:
1. if CLI is the canonical surface, CLI tests are required
2. if fixtures are canonical, fixture-runner tests are required
3. if both are canonical, both must be tested at their operator surface

Acceptance:
1. proof is attached at the same layer users operate
2. drift classification remains visible at that same layer

## 5. Source-of-Truth Docs To Update On Closeout

Potentially affected docs:
1. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md`
2. `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md`
3. `docs/specs/RUNTIME_INVARIANTS.md`
4. `scripts/README.md`

Minimum required update set:
1. every active spec or script reference that names the canonical replay/harness surface

## 6. Likely Runtime/Test Files To Change

Likely runtime or script paths:
1. `orket/interfaces/cli.py`
2. `orket/runtime/protocol_replay.py`
3. `orket/runtime/protocol_determinism_campaign.py`
4. `scripts/protocol/run_protocol_replay_compare.py`
5. `scripts/protocol/run_protocol_determinism_campaign.py`

Potential new paths if fixture-based golden runs remain in scope:
1. a fixture loader/validator module under `orket/runtime/` or `scripts/protocol/`
2. fixture data stored under a canonical location to be chosen by the direct implementation plan

Likely proof paths:
1. `tests/runtime/test_protocol_replay.py`
2. `tests/runtime/test_protocol_determinism_campaign.py`
3. `tests/scripts/test_run_protocol_replay_compare.py`
4. `tests/scripts/test_run_protocol_determinism_campaign.py`
5. new CLI or fixture-runner tests at the chosen operator layer

## 7. Verification Requirements

Required eventual proof layers:
1. `contract`
   - fixture schema tests if fixtures remain in scope
2. `integration`
   - replay-engine and comparison behavior
3. `end-to-end`
   - CLI or user-facing harness tests for the chosen canonical surface

Required governance proof:
1. `python scripts/governance/check_docs_project_hygiene.py`

## 8. Completion Criteria

This requirements packet is complete when:
1. the canonical replay/harness interface is explicit
2. fixture scope is either specified or truthfully narrowed out
3. replay logic is prevented from splitting into parallel authorities
4. exact source-of-truth docs and likely runtime files are identified
5. the direct implementation plan can begin without reopening interface identity questions

## 9. Next Artifact

After acceptance, create a direct implementation plan for SPC-02 closeout or a source-of-truth narrowing change if `protocol replay is canonical` is chosen without a fixture-based harness.
