# Control-Plane Packet V1 Index
Last updated: 2026-03-26
Status: Active
Owner: Orket Core

## Purpose

Extract the accepted ControlPlane contract family into a durable spec index before implementation planning.

This index exists so the implementation plan can point at a stable spec authority instead of depending on loosely related draft notes.

## Canonical authority set

The accepted ControlPlane authority family currently consists of:

1. [docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md)
2. [docs/projects/ControlPlane/orket_control_plane_packet/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md)
3. [docs/projects/ControlPlane/orket_control_plane_packet/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md)
4. [docs/projects/ControlPlane/orket_control_plane_packet/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md)
5. [docs/projects/ControlPlane/orket_control_plane_packet/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md)
6. [docs/projects/ControlPlane/orket_control_plane_packet/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md)
7. [docs/projects/ControlPlane/orket_control_plane_packet/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md)
8. [docs/projects/ControlPlane/orket_control_plane_packet/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md)
9. [docs/projects/ControlPlane/orket_control_plane_packet/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md)
10. [docs/projects/ControlPlane/orket_control_plane_packet/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md)
11. [docs/projects/ControlPlane/orket_control_plane_packet/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md)
12. [docs/projects/ControlPlane/orket_control_plane_packet/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md)

Supporting but non-overriding planning documents:

1. [docs/projects/ControlPlane/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md](docs/projects/ControlPlane/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md)
2. [docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md](docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md)
3. [docs/projects/ControlPlane/orket_control_plane_packet/09_OS_MASTER_PLAN.md](docs/projects/ControlPlane/orket_control_plane_packet/09_OS_MASTER_PLAN.md)
4. [docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md)
5. [docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md)

## Authority precedence

When multiple docs touch the same topic, precedence is:

1. [docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md) for shared nouns and enums
2. the specific requirement document for semantic rules and acceptance criteria
3. [docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md) for the archived convergence-lane execution record
4. [docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md) for archived packet-v2 execution order only
5. [docs/projects/ControlPlane/orket_control_plane_packet/09_OS_MASTER_PLAN.md](docs/projects/ControlPlane/orket_control_plane_packet/09_OS_MASTER_PLAN.md) for architecture rationale only

## Architecture alignment

`FinalTruthRecord.result_class` remains aligned with the result vocabulary in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The ControlPlane packet adds closure fields around that vocabulary.
It does not silently create a second result regime.
