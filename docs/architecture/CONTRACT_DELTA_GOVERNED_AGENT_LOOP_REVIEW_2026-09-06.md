# Contract Delta: Governed Agent Loop Implementation Review

Status: Accepted planning revision; runtime implementation pending

## Summary

- Change title: Make agent invocation, compatibility, recovery, and proof gates
  implementable and truthful.
- Owner: Orket Core
- Date: 2026-09-06
- Affected contracts and plans:
  `docs/specs/GOVERNED_AGENT_LOOP_V1.md`,
  `docs/architecture/CONTRACT_DELTA_GOVERNED_AGENT_LOOP_V1_2026-09-06.md`,
  `docs/projects/governed-agent-loop/GOVERNED_CONTINUOUS_AGENT_IMPLEMENTATION_PLAN.md`,
  and its three component plans.
- Authorization: user requested review and improvements to the recent plans.
  This revision refines the existing implementation direction.

## Delta

- Current planned behavior had no concrete parent/child capability boundary,
  assumed optional manifest metadata forced old-host refusal, conflated import
  guards with containment, and required SDK release before its own host proof.
- Revised behavior requires a bounded host capability broker, authoritative
  per-call budget reservations, parent-bound invocation identity, and a runtime
  handshake plus mandatory `agent.iteration.v1` capability in the existing v0
  manifest. Existing synchronous/model capability contracts remain compatible.
- Existing `orket_extension_sdk/manifest.py` drops unknown fields; a read-only
  validation probe confirmed a supplied agent-version field was not retained.
  Strict validation must reject the unknown required capability on old hosts;
  the runtime handshake protects entry through permissive legacy paths.
- V1 explicitly admits trusted extension code. Import guards and subprocesses
  provide no hostile-code OS isolation. Same-process roles are context
  partitions, not separate security principals.
- Agent invocation must reuse extension execution beneath independent-run
  publication. Parent objectives cannot be finalized by child invocation success.
- Claims and calls require fencing; uncertain writes require reconciliation,
  and expired leases cannot imply exactly-once effects or confirmed termination.
- Model usage is host-recorded. Repairs count against budgets; unknown usage
  retains conservative reservations. Memory mutations commit only after result
  validation, while consumed inference and host audit records survive a crash.
- The selected turn-tool integration must prove its existing issue namespace,
  approval, checkpoint, and target lineage. This revision does not widen the
  existing approval surface or claim agent approve-to-continue is implemented.
- Two-iteration report fixtures and equal-budget single/multi-model comparisons
  replace one-shot invocation as sufficient loop proof.
- Completed requirements history moves to the phase archive. The umbrella and
  component plans remain active; roadmap position is unchanged.

## Migration Plan

1. Compatibility window: existing v0 workloads remain supported; agent admission
   remains unavailable until schemas, broker, manifest, and runtime proof land.
2. Migration steps: implement the minimum SDK development wheel and external
   fixture with the host adapter; retain final SDK publication until joint proof.
   B2 remains owned by architectural-truth and gates affected API/supervisor work.
3. Validation gates: old/new built-package combinations, broker disconnect and
   forged/stale calls, bounded teardown, usage loss, argument/approval drift,
   crash reconciliation, and two-iteration live acceptance. Record actual
   supported SDK/core versions rather than inferring them from a minor bump.

## Rollback Plan

1. Rollback trigger: the broker, admission guard, invocation mapping, or effect
   integration cannot satisfy its declared invariant.
2. Rollback steps: keep agent admission disabled and revise the failing slice;
   existing generic extension behavior remains the current runtime path.
3. Data/state recovery notes: this change edits documentation only and creates
   no runtime state. Future rollback must retain audit and uncertain-effect truth.

## Versioning Decision

- Version bump type: no package bump for this documentation review.
- Effective version/date: planning contract revised 2026-09-06; runtime support
  remains pending the active implementation gates.
- Downstream impact: SDK and host implementers must use the broker, capability
  marker, handshake, and shared packaged schemas. No current package gains new
  runtime capabilities from this document.
