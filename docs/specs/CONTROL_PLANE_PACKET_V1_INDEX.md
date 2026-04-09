# Control-Plane Packet V1 Index
Last updated: 2026-04-09
Status: Active
Owner: Orket Core

## Purpose

Index the accepted ControlPlane contract family as the durable post-closeout spec authority.

## Canonical authority set

The accepted ControlPlane authority family currently consists of:

1. [docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md)
2. [docs/specs/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md](docs/specs/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md)
3. [docs/specs/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md](docs/specs/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md)
4. [docs/specs/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md](docs/specs/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md)
5. [docs/specs/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md](docs/specs/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md)
6. [docs/specs/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md](docs/specs/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md)
7. [docs/specs/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md](docs/specs/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md)
8. [docs/specs/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md](docs/specs/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md)
9. [docs/specs/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md](docs/specs/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md)
10. [docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md](docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md)
11. [docs/specs/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md](docs/specs/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md)
12. [docs/specs/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md](docs/specs/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md)

The former project-local packet files are preserved under `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/` and are not active authority.

Supporting but non-overriding governance and historical documents:

1. [docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md](docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md)
2. [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md)
3. [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CONTROL_PLANE_PROJECT_CLOSEOUT_READINESS_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CONTROL_PLANE_PROJECT_CLOSEOUT_READINESS_IMPLEMENTATION_PLAN.md)
4. [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md)
5. [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md)
6. [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/09_OS_MASTER_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/09_OS_MASTER_PLAN.md)
7. [docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CONTROL_PLANE_WORKLOAD_RUN_AUTHORITY_FOLLOW_ON_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CONTROL_PLANE_WORKLOAD_RUN_AUTHORITY_FOLLOW_ON_IMPLEMENTATION_PLAN.md)
8. [docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_REOPEN_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_REOPEN_IMPLEMENTATION_PLAN.md)
9. [docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md)
10. [docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md)

## Authority precedence

When multiple docs touch the same topic, precedence is:

1. [docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md) for shared nouns and enums
2. the specific requirement document for semantic rules and acceptance criteria
3. [docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md](docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md) for the active governed workload-authority lock and start-path matrix
4. [docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/CLOSEOUT.md) for the project closeout record
5. [docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CONTROL_PLANE_WORKLOAD_RUN_AUTHORITY_FOLLOW_ON_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-WORKSTREAM-1-FOLLOW-ON-CLOSEOUT/CONTROL_PLANE_WORKLOAD_RUN_AUTHORITY_FOLLOW_ON_IMPLEMENTATION_PLAN.md) for the closed residual Workstream 1 execution record
6. [docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_REOPEN_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-CONVERGENCE-REOPEN-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_REOPEN_IMPLEMENTATION_PLAN.md) for the completed 2026-04-09 convergence-reopen execution record
7. [docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md) for the archived convergence-lane execution record
8. [docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md](docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/13_CONTROL_PLANE_IMPLEMENTATION_PLAN.md) for archived packet-v2 execution order only

## Project closeout posture

ControlPlane project closeout completed on `2026-04-09`.

Durable packet authority now lives under `docs/specs/`, the active governed workload-authority matrix now lives under `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`, and the historical project record is archived under `docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/`.

## Architecture alignment

`FinalTruthRecord.result_class` remains aligned with the result vocabulary in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The ControlPlane packet adds closure fields around that vocabulary.
It does not silently create a second result regime.
