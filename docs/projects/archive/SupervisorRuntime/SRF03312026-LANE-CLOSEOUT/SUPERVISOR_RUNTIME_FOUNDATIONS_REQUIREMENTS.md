# Supervisor Runtime Foundations Requirements
Last updated: 2026-03-31
Status: Completed (archived accepted requirements authority)
Owner: Orket Core
Lane type: Supervisor runtime foundations / archived Packet 1 requirements companion

Implementation archive: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_IMPLEMENTATION_PLAN.md`
Closeout authority: `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
Contract delta: `docs/architecture/CONTRACT_DELTA_SUPERVISOR_RUNTIME_PACKET1_APPROVAL_SLICE_REALIGNMENT_2026-03-31.md`

## Authority posture

This archived file records the accepted requirements that closed the SupervisorRuntime Packet 1 lane.

The active durable Packet 1 contract surfaces remain:
1. `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`
2. `docs/specs/SUPERVISOR_RUNTIME_SESSION_BOUNDARY_V1.md`
3. `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`
4. `docs/specs/SUPERVISOR_RUNTIME_EXTENSION_VALIDATION_V1.md`

Before closeout, the approval-checkpoint slice was realigned from the originally planned governed turn-tool destructive-mutation path to the governed kernel `NEEDS_APPROVAL` lifecycle on the default `session:<session_id>` namespace scope.
That realignment was required because the governed turn-tool path currently truthfully publishes approval requests and terminal stop outcomes, but does not provide an approve-to-continue execution path.
The contract delta above records that boundary change.

## Cross-lane invariants that remained fixed

1. the host remains the sole runtime authority
2. checkpoint presence, snapshot presence, or saved state presence never authorizes continuation by implication
3. operator command, risk acceptance, and attestation remain distinct from runtime observation and closure truth
4. session memory, profile memory, and workspace memory remain distinguishable
5. installability and validation never create a second hidden runtime authority center

## Final accepted Packet 1 selection

1. approval-checkpoint runtime behavior
   - selected capability class: governed kernel `action.tool_call` proposals whose admission decision is `NEEDS_APPROVAL`
   - namespace scope: default `session:<session_id>` only
   - lifecycle: system-created pending hold, operator inspect, operator approve or deny, then explicit runtime commit or terminal stop
   - continuation rule: no resume by implication; Packet 1 does not define a separate manual resume API for this slice
   - checkpoint rule: no checkpoint-backed continuation path is admitted; any surfaced checkpoint remains inspection-only and `resume_forbidden`
2. session and context-provider behavior
   - host-owned `session_id` created at `POST /v1/interactions/sessions`
   - subordinate turn attachment at `POST /v1/interactions/{session_id}/turns`
   - selected context-provider inputs limited to `session_params`, `input_config`, `turn_params`, `workload_id`, `department`, `workspace`, resolved extension-manifest `required_capabilities` when the extension path is used, and authenticated operator context only where approval resolution is involved
3. operator control surface behavior
   - canonical inspection path: `GET /v1/approvals/{approval_id}`
   - canonical action path: `POST /v1/approvals/{approval_id}/decision`
   - canonical projection source: durable control-plane records summarized on the approval read model
4. host-owned extension contract behavior
   - canonical manifest family: SDK-first `extension.yaml` / `extension.yml` / `extension.json`
   - admitted Packet 1 fields: `manifest_version`, `extension_id`, `extension_version`, and `workloads[*]` with `workload_id`, `entrypoint`, and `required_capabilities`
   - canonical validation path: `orket ext validate <extension_root> --strict --json`
   - unsupported-host-version rule: only `manifest_version: v0` is admitted and all other manifest families fail closed

## Packet 1 non-goals that remained fixed

1. broad session cleanup, retention, or memory policy
2. general replay infrastructure beyond the selected reconstruction boundary
3. broader operator-platform work beyond the shipped approval inspection and action surfaces
4. extension marketplace, install-source plurality, or cloud distribution work
5. support for multiple manifest contract families in parallel

## Outcome

This requirements packet closed successfully because:
1. the four admitted behavior families were extracted into durable `docs/specs/` contracts
2. the bounded implementation lane completed without reopening broad scope questions
3. one real-path live proof passed for the selected governed approval slice
4. roadmap, archive, and source-of-truth docs now tell one completed authority story

## Archived record

1. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_REQUIREMENTS.md`
2. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/SUPERVISOR_RUNTIME_FOUNDATIONS_IMPLEMENTATION_PLAN.md`
3. `docs/projects/archive/SupervisorRuntime/SRF03312026-LANE-CLOSEOUT/CLOSEOUT.md`
