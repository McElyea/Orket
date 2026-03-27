# Orket Control-Plane Packet

This packet now represents the accepted authority set required to move from architecture direction into implementation planning.

## Included authorities

- `00_CONTROL_PLANE_FOUNDATION_PACKET.md`
- `00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`
- `00B_CURRENT_STATE_CROSSWALK.md`
- `01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md`
- `02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md`
- `03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md`
- `04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md`
- `05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md`
- `06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md`
- `07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md`
- `08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md`
- `09_OS_MASTER_PLAN.md`
- `10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md`
- `11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md`
- `12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md`
- `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md`

## Authority posture

This packet is now split into four roles:

1. shared authority:
   - `00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`
2. current-state honesty:
   - `00B_CURRENT_STATE_CROSSWALK.md`
3. requirement authority:
   - `01` through `08`
   - `10` through `12`
4. planning:
   - `09_OS_MASTER_PLAN.md` for architecture direction only
   - `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md` for archived execution sequencing

## Important guardrails

1. `Reservation` is first-class.
2. `FinalTruthRecord` is first-class.
3. `recovering` is control-plane recovery activity, not ordinary workload execution.
4. Operator risk acceptance is never evidence of world state.
5. Operator attestation is explicit and never equivalent to adapter observation.
6. The effect journal is a normative authority surface, not mere storage.
7. The namespace contract is slim now rather than deferred entirely.

## Spec extraction

The accepted packet is indexed for planning under:

- [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)

## Planning status

The packet remains the active requirements authority.

The implementation lane is closed and archived at:

- `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md`

The architecture-direction companion remains:

- `09_OS_MASTER_PLAN.md`

Staging-only convergence drafts may exist under `docs/projects/ControlPlane/`, but they do not reopen implementation authority unless `docs/ROADMAP.md` adds a new explicit ControlPlane lane that points to their canonical implementation plan path.
