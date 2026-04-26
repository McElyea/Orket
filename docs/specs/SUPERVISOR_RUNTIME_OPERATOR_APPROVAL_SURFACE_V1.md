# Supervisor Runtime Operator Approval Surface V1

Last updated: 2026-04-25
Status: Active
Owner: Orket Core
Source requirements: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
Implementation closeout authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
2. `docs/API_FRONTEND_CONTRACT.md`
3. `CURRENT_AUTHORITY.md`

## Authority posture

This document is the active durable contract authority for the completed SupervisorRuntime Packet 1 operator approval action and projection surface.

It governs one canonical operator action path and one canonical operator inspection path for the selected governed kernel approval slice and the shared approval read model.
It does not create a general operator platform and it does not authorize endpoint-local truth invention.

## Purpose

Define the smallest truthful operator surface that can inspect and resolve the selected approval-checkpoint runtime slice without becoming a hidden runtime authority center.
The selected lifecycle family is defined by `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`; as of this update, it includes governed kernel `NEEDS_APPROVAL` plus the bounded governed turn-tool `write_file`, `create_directory`, and `create_issue` slices.

## Scope

In scope:
1. one canonical inspection path: `GET /v1/approvals/{approval_id}`
2. one canonical action path: `POST /v1/approvals/{approval_id}/decision`
3. one canonical projection source: durable control-plane records summarized on the approval read model
4. one explicit split between runtime truth, operator-visible projections, and operator action records

Out of scope:
1. a broad operator workbench or dashboard platform
2. multiple competing approval detail surfaces
3. endpoint-local closure truth
4. any rule that lets operator commands rewrite runtime-owned observation or final-truth records

## Decision lock

The following remain fixed for Packet 1:
1. operator surfaces project and request; they do not own runtime truth
2. the selected inspection path is `GET /v1/approvals/{approval_id}`
3. the selected action path is `POST /v1/approvals/{approval_id}/decision`
4. the selected projection source is durable control-plane records summarized on the approval read model
5. missing or drifted source data fails closed rather than producing false operator-visible certainty

## Canonical surfaces

The selected Packet 1 operator surfaces are:
1. inspection: `GET /v1/approvals/{approval_id}`
2. action: `POST /v1/approvals/{approval_id}/decision`

The approval list path may remain available for discovery, but Packet 1 treats the detail path above as the canonical inspection surface for the admitted behavior family.

## Projection source contract

The selected projection source is durable control-plane lineage summarized on the approval read model.

At minimum, when present, the projection source may summarize:
1. reservation
2. operator action
3. run
4. attempt
5. step
6. checkpoint
7. effect-journal
8. final-truth records

Packet 1 does not allow the approval surface to substitute free-form narration for those runtime-owned sources.

## Field-split contract

The selected Packet 1 field split is:
1. runtime-authoritative target truth remains in durable control-plane records
2. operator-visible projection fields are summaries derived from those records on the approval read model
3. operator actions or requests remain distinct operator-command or operator-risk-acceptance surfaces
4. endpoint-local response shaping must not invent target-side truth when source records are missing, contradictory, or drifted

## Action contract

For the selected Packet 1 surface:
1. the decision request requires `decision`
2. `notes` and `edited_proposal` may be accepted as optional payload members
3. Packet 1 still admits only the selected approve-or-deny lifecycle for the chosen runtime slice
4. optional payload members must not silently broaden Packet 1 into a second execution-authority path
5. conflicting or contradictory decisions must fail closed rather than rewriting prior runtime truth
6. admitting `create_directory` does not add a route, decision value, payload member, or manual resume surface; it only adds one bounded tool name to the companion checkpoint contract.

## Fail-closed projection behavior

The operator approval surface must fail closed when:
1. the selected approval id is missing
2. the target-side projection source is missing or drifted for a field that would otherwise read like runtime truth
3. operator-visible action history conflicts with the target-side authoritative record set
4. a consumer would need the endpoint to invent closure truth or continuity lineage that the source records do not support

Fail-closed behavior may omit a projection block or reject the request, but it must not fabricate coherence.

## Canonical seams and proof entrypoints

Current Packet 1 seams:
1. `GET /v1/approvals/{approval_id}`
2. `POST /v1/approvals/{approval_id}/decision`

Current proof entrypoints:
1. `python -m pytest -q tests/interfaces/test_api_approvals.py`
2. `python -m pytest -q tests/interfaces/test_api_nervous_system_operator_surfaces.py`

## Contract maintenance rules

If this contract changes materially, the same change must update:
1. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md` when the selected lifecycle or checkpoint story changes
3. `docs/API_FRONTEND_CONTRACT.md` when the operator routes or payloads change
4. `CURRENT_AUTHORITY.md` when the active spec set or projection-source authority story changes
5. `docs/RUNBOOK.md` when operator-visible inspection or action behavior changes
