# Supervisor Runtime Approval Checkpoint V1

Last updated: 2026-04-01
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
Implementation closeout authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
2. `docs/API_FRONTEND_CONTRACT.md`
3. `CURRENT_AUTHORITY.md`

## Authority posture

This document is the active durable contract authority for the completed SupervisorRuntime Packet 1 approval-checkpoint family.

It selects three bounded governed approval lifecycles that have now shipped.
It does not create a broad approval platform and it does not imply approve-to-continue support on other approval-producing paths.

## Purpose

Define the fail-closed approval-checkpoint runtime contract for:
1. governed kernel `action.tool_call` proposals that require destructive approval on the default `session:<session_id>` namespace scope
2. one governed turn-tool `write_file` approval-required slice on the default `issue:<issue_id>` namespace scope
3. one governed turn-tool `create_issue` approval-required slice on the default `issue:<issue_id>` namespace scope

## Scope

In scope:
1. governed kernel `NEEDS_APPROVAL` admission for destructive tool-call proposals on `session:<session_id>`
2. governed turn-tool `write_file` approval-required admission on `issue:<issue_id>`
3. governed turn-tool `create_issue` approval-required admission on `issue:<issue_id>`
4. one pending / inspect / approve-or-deny / explicit continue-or-stop lifecycle per admitted slice
5. one cold continuation rule for the kernel slice: no resume by implication; any surfaced checkpoint remains `resume_forbidden`
6. one bounded same-attempt pre-effect continuation rule for the governed turn-tool `write_file` and `create_issue` slices only
7. one attribution and evidence story rooted in durable control-plane records

Out of scope:
1. governed turn-tool approve-to-continue beyond `write_file` and `create_issue`
2. broader namespace scopes
3. same-attempt or replacement-attempt resume authority derived from checkpoint presence outside the selected `write_file` plus `create_issue` slices
4. general approval-platform or replay-platform behavior beyond the selected slice

## Decision lock

The following remain fixed for Packet 1:
1. the host remains the sole runtime authority
2. checkpoint presence never authorizes continuation by implication
3. operator approval or denial remains distinct from runtime observation, effect, and final-truth records
4. Packet 1 does not define a separate manual resume API for this slice
5. the only admitted turn-tool approval-required continuation slices are `write_file` and `create_issue`
6. the only admitted turn-tool approval-required namespace scope is the default `issue:<issue_id>` path
7. missing or drifted approval, reservation, lease, namespace, or target-run prerequisites fail closed

## Canonical capability class

The admitted Packet 1 capability classes are:
1. gated action: governed kernel `action.tool_call` proposal whose admission decision is `NEEDS_APPROVAL`
2. requester: authenticated caller on `POST /v1/kernel/admit-proposal`
3. approver or rejector: an authenticated operator on `POST /v1/approvals/{approval_id}/decision`
4. namespace scope: the default `session:<session_id>` path only for the kernel slice
5. gated action: governed turn-tool `write_file` request with `request_type=tool_approval` and `reason=approval_required_tool:write_file`
6. gated action: governed turn-tool `create_issue` request with `request_type=tool_approval` and `reason=approval_required_tool:create_issue`
7. requester: runtime-owned governed turn-tool dispatch on the default `issue:<issue_id>` path only
8. approver or rejector: an authenticated operator on `POST /v1/approvals/{approval_id}/decision`
9. runtime truth owner: durable control-plane records for the selected governed target run, attempt, step, effect-journal, and final-truth lineage when present

Broader scope declarations are outside Packet 1 and must fail closed rather than silently widening the selected capability class.

## Lifecycle contract

For the selected Packet 1 slice:
1. runtime creates a pending approval hold when kernel admit returns `NEEDS_APPROVAL`
2. runtime creates a pending approval hold when governed turn-tool dispatch encounters the admitted `write_file` or `create_issue` slice before execution
3. operator inspection occurs on `GET /v1/approvals/{approval_id}`
4. operator resolution occurs on `POST /v1/approvals/{approval_id}/decision`
5. `approve` on the kernel slice allows the already-selected governed kernel commit path to continue only through runtime-owned commit logic on `POST /v1/kernel/commit-proposal`
6. `deny` on the kernel slice blocks that commit path without silent fallback or implicit continuation
7. `approve` on the admitted turn-tool `write_file` or `create_issue` slice allows one runtime-owned same-governed-run continue step by replaying the accepted pre-effect checkpoint on the already-selected `control_plane_target_ref`
8. `deny` on the admitted turn-tool `write_file` or `create_issue` slice terminal-stops that same governed turn-tool run without hidden continuation
9. Packet 1 does not define a separate manual resume API for either selected slice
10. checkpoint artifacts, when surfaced on these slices, remain inspection and attribution surfaces except for the admitted runtime-owned `write_file` plus `create_issue` same-attempt continuation rule below

## Checkpoint and continuation rule

The selected continuation rules are intentionally bounded:
1. Packet 1 does not require or expose a checkpoint-backed continuation path for the kernel `NEEDS_APPROVAL` slice
2. any checkpoint summary surfaced on the kernel slice must remain inspection-only and, if resumability is published, it must be `resume_forbidden`
3. the admitted turn-tool `write_file` and `create_issue` slices may consume the already-accepted same-attempt pre-effect checkpoint only through runtime-owned continuation on the already-selected governed run
4. checkpoint presence never authorizes that turn-tool continuation by implication; the admitted approved `tool_approval` decision is required
5. replay or inspection may describe the checkpoint boundary, but may not turn it into broader execution authority
6. missing or drifted approval lineage, reservation or lease authority, namespace authority, or selected target-run identity blocks continuation
7. Packet 1 still does not standardize replacement-attempt continuation or any broader turn-tool approval-required family

## Fail-closed preconditions

The selected path must fail closed when any of the following is missing, drifted, or contradictory:
1. pending approval authority for the selected kernel target run
2. authenticated operator decision on the canonical approval decision path
3. target-run identity alignment between approval, reservation, and runtime projection source
4. session namespace authority required by the target run's current control-plane state
5. `approval_id` on the commit path when the admission decision requires approval
6. issue namespace authority required by the admitted turn-tool `write_file` or `create_issue` target run
7. admitted `write_file` or `create_issue` request identity alignment between approved request payload, selected target run, and resumed checkpoint snapshot

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
5. governed turn-tool `write_file` and `create_issue` dispatch on the default `issue:<issue_id>` path using `request_type=tool_approval`, `reason=approval_required_tool:<tool_name>`, and the existing `control_plane_target_ref`

Current proof entrypoints:
1. `python -m pytest -q tests/interfaces/test_api_approvals.py`
2. `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py`
3. `python -m pytest -q tests/scripts/test_nervous_system_live_evidence.py`
4. `ORKET_DISABLE_SANDBOX=1 python scripts/nervous_system/run_nervous_system_live_evidence.py`
5. `python -m pytest -q tests/application/test_turn_executor_middleware.py -k "write_file_approval_resume_continues_same_governed_run or create_issue_approval_resume_continues_same_governed_run"`
6. `python -m pytest -q tests/application/test_engine_approvals.py`
7. `python -m pytest -q tests/application/test_orchestrator_epic.py -k "pending_gate_callback_creates_tool_approval_request or pending_gate_callback_creates_create_issue_tool_approval_request"`

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md` when the selected approval operator surface changes
3. `docs/API_FRONTEND_CONTRACT.md` when routes or payloads change
4. `CURRENT_AUTHORITY.md` when the active spec set or approval authority story changes
5. `docs/RUNBOOK.md` when operator-visible approval behavior changes
