# SPC-02 Golden Harness Closeout Implementation Plan

Last updated: 2026-03-13
Status: Active
Owner: Orket Core
Parent lane: `docs/projects/runtime-stability-closeout/IMPLEMENTATION-PLAN.md`
Source requirements: `docs/projects/runtime-stability-green-requirements/04-SPC-02-GOLDEN-HARNESS-REQUIREMENTS.md`

## 1. Decision Lock

Chosen closeout target: `protocol replay is canonical`.
Explicitly excluded target(s): fixture-based golden harness as canonical and any dual-surface closeout that keeps both fixture replay and protocol replay as equal authorities.

## 2. Objective

Close SPC-02 by making the shipped protocol replay surface the only active replay/harness closeout claim and by proving that surface at the same operator layer users invoke.

## 3. In Scope

1. Narrow the active replay/harness requirements to the shipped `protocol replay`, `compare`, and `campaign` surfaces.
2. Keep replay logic single-sourced in the existing protocol replay engine.
3. Add or tighten operator-layer proof at the CLI and script surfaces already shipped.

## 4. Explicitly Out Of Scope

1. Introducing a new canonical `golden/<test>` fixture runner.
2. Defining canonical fixture storage for active closeout scope.
3. Maintaining a dual-surface contract where fixture replay and protocol replay are both first-class authorities.

## 5. Planned Changes

### 5.1 Source-Of-Truth Narrowing

1. Update `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` so Focus Item 2 names the protocol replay surface instead of `orket run golden/<test>` and `orket replay golden/<test>`.
2. Update any remaining active spec or script docs that still imply fixture-based golden authority, including:
   1. `docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md` if replay references remain there
   2. `docs/specs/RUNTIME_INVARIANTS.md` if replay terminology drifts there
   3. `scripts/README.md` if it still describes golden fixtures as active operator surface

### 5.2 Proof Hardening

1. Keep `tests/runtime/test_protocol_replay.py` as `integration` proof for replay reconstruction.
2. Keep `tests/runtime/test_protocol_determinism_campaign.py` as `integration` proof for determinism campaigns.
3. Keep `tests/scripts/test_run_protocol_replay_compare.py` and `tests/scripts/test_run_protocol_determinism_campaign.py` as `integration` proof for the script wrappers.
4. Tighten `tests/interfaces/test_cli_protocol_replay.py` as the primary `end-to-end` proof for the canonical operator surface.
5. Tighten `tests/interfaces/test_cli_protocol_parity_campaign.py` as `end-to-end` proof if campaign invocation or output wording changes.

### 5.3 Runtime Code Changes

1. Prefer zero replay-engine changes.
2. Only modify `orket/interfaces/cli.py`, `scripts/protocol/run_protocol_replay_compare.py`, or `scripts/protocol/run_protocol_determinism_campaign.py` if operator-facing help, naming, or output shape currently drifts from the narrowed requirement text.

## 6. Verification Plan

1. `integration`: `tests/runtime/test_protocol_replay.py`
2. `integration`: `tests/runtime/test_protocol_determinism_campaign.py`
3. `integration`: `tests/scripts/test_run_protocol_replay_compare.py`
4. `integration`: `tests/scripts/test_run_protocol_determinism_campaign.py`
5. `end-to-end`: `tests/interfaces/test_cli_protocol_replay.py`
6. `end-to-end`: `tests/interfaces/test_cli_protocol_parity_campaign.py` if CLI campaign wording changes
7. Governance: `python scripts/governance/check_docs_project_hygiene.py`

## 7. Exit Criteria

1. Active specs no longer promise a canonical fixture-based golden interface.
2. The protocol replay surface is the only active replay/harness authority for closeout.
3. CLI and script-layer proof pass against that narrowed claim.
