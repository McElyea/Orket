# Supervisor Runtime Approval Checkpoint V1

Last updated: 2026-03-31
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
Implementation closeout authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
2. `docs/API_FRONTEND_CONTRACT.md`
3. `CURRENT_AUTHORITY.md`

## Authority posture

This document is the active durable contract authority for the completed SupervisorRuntime Packet 1 approval-checkpoint runtime slice.

It selects one bounded governed approval lifecycle that shipped in Packet 1.
It does not create a broad approval platform and it does not imply approve-to-continue support on other approval-producing paths.

## Purpose

Define one fail-closed approval-checkpoint runtime contract for governed kernel `action.tool_call` proposals that require destructive approval on the default `session:<session_id>` namespace scope.

## Scope

In scope:
1. governed kernel `NEEDS_APPROVAL` admission for destructive tool-call proposals on `session:<session_id>`
2. one pending / inspect / approve-or-deny / explicit commit-or-stop lifecycle
3. one cold continuation rule: no resume by implication; any surfaced checkpoint remains `resume_forbidden`
4. one attribution and evidence story rooted in durable control-plane records

Out of scope:
1. governed turn-tool approve-to-continue lifecycle
2. broader namespace scopes
3. same-attempt or replacement-attempt resume authority derived from checkpoint presence
4. general approval-platform or replay-platform behavior beyond the selected slice

## Decision lock

The following remain fixed for Packet 1:
1. the host remains the sole runtime authority
2. checkpoint presence never authorizes continuation by implication
3. operator approval or denial remains distinct from runtime observation, effect, and final-truth records
4. Packet 1 does not define a separate manual resume API for this slice
5. missing or drifted approval, reservation, lease, namespace, or target-run prerequisites fail closed

## Canonical capability class

The admitted Packet 1 capability class is:
1. gated action: governed kernel `action.tool_call` proposal whose admission decision is `NEEDS_APPROVAL`
2. requester: authenticated caller on `POST /v1/kernel/admit-proposal`
3. approver or rejector: an authenticated operator on `POST /v1/approvals/{approval_id}/decision`
4. namespace scope: the default `session:<session_id>` path only
5. runtime truth owner: durable control-plane records for the selected governed kernel target run, attempt, step, effect-journal, and final-truth lineage when present

Broader scope declarations are outside Packet 1 and must fail closed rather than silently widening the selected capability class.

## Lifecycle contract

For the selected Packet 1 slice:
1. runtime creates a pending approval hold when kernel admit returns `NEEDS_APPROVAL`
2. operator inspection occurs on `GET /v1/approvals/{approval_id}`
3. operator resolution occurs on `POST /v1/approvals/{approval_id}/decision`
4. `approve` allows the already-selected governed kernel commit path to continue only through runtime-owned commit logic on `POST /v1/kernel/commit-proposal`
5. `deny` blocks that commit path without silent fallback or implicit continuation
6. Packet 1 does not define a separate manual resume API for this selected slice
7. checkpoint artifacts, when surfaced on this slice, remain inspection and attribution surfaces only

## Checkpoint and continuation rule

The selected continuation rule is intentionally cold:
1. Packet 1 does not require or expose a checkpoint-backed continuation path for the selected slice
2. any checkpoint summary surfaced on this slice must remain inspection-only and, if resumability is published, it must be `resume_forbidden`
3. replay or inspection may describe the checkpoint boundary, but may not turn it into execution authority
4. missing or drifted approval lineage, reservation or lease authority, or selected target-run identity blocks continuation
5. Packet 1 does not standardize same-attempt continuation or replacement-attempt continuation for this slice

## Fail-closed preconditions

The selected path must fail closed when any of the following is missing, drifted, or contradictory:
1. pending approval authority for the selected kernel target run
2. authenticated operator decision on the canonical approval decision path
3. target-run identity alignment between approval, reservation, and runtime projection source
4. session namespace authority required by the target run's current control-plane state
5. `approval_id` on the commit path when the admission decision requires approval

Failure to satisfy those preconditions must block continuation rather than creating a fallback continuation story.

## Evidence and attribution contract

The selected Packet 1 approval-checkpoint slice must remain attributable to:
1. the approval request
2. the operator decision
3. the target run and attempt
4. the target step, effect-journal, and final-truth records when present
5. dependent reservation, lease, and resource refs when present

Packet 1 does not allow a narrated approval outcome that is not backed by durable runtime-owned evidence.

## Canonical seams and proof entrypoints

Current Packet 1 seams:
1. `POST /v1/kernel/admit-proposal`
2. `GET /v1/approvals/{approval_id}`
3. `POST /v1/approvals/{approval_id}/decision`
4. `POST /v1/kernel/commit-proposal`

Current proof entrypoints:
1. `python -m pytest -q tests/interfaces/test_api_approvals.py`
2. `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py`
3. `python -m pytest -q tests/scripts/test_nervous_system_live_evidence.py`
4. `ORKET_DISABLE_SANDBOX=1 python scripts/nervous_system/run_nervous_system_live_evidence.py`

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md` when the selected approval operator surface changes
3. `docs/API_FRONTEND_CONTRACT.md` when routes or payloads change
4. `CURRENT_AUTHORITY.md` when the active spec set or approval authority story changes
5. `docs/RUNBOOK.md` when operator-visible approval behavior changes
