from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.core.contracts import (
    WORKLOAD_CONTRACT_VERSION_V1,
    WorkloadRecord,
    build_control_plane_workload_record_from_workload_contract,
)
from orket.schema import EpicConfig

CARDS_CONTROL_PLANE_WORKLOAD_ID = "cards-epic-execution"


def build_cards_workload_contract(
    *,
    epic: EpicConfig,
    run_id: str,
    build_id: str,
    workspace: Path,
    department: str,
) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    for issue in epic.issues:
        units.append(
            {
                "unit_id": f"card:{issue.id}",
                "card_id": issue.id,
                "seat": issue.seat,
                "priority": issue.priority,
                "depends_on": list(issue.depends_on or []),
            }
        )

    observability_root = workspace / "observability" / run_id
    required_materials = [
        {"kind": "asset", "value": f"epics/{epic.name}.json"},
        {"kind": "asset", "value": f"teams/{epic.team}.json"},
        {"kind": "asset", "value": f"environments/{epic.environment}.json"},
    ]
    expected_artifacts = [
        str((workspace / "agent_output" / "observability" / "runtime_events.jsonl").as_posix()),
        str((observability_root.as_posix())),
    ]
    summary_targets = [str((workspace / "agent_output" / "observability" / "runtime_events.jsonl").as_posix())]
    provenance_targets = [str((workspace / "observability" / run_id).as_posix())]

    return {
        "workload_contract_version": WORKLOAD_CONTRACT_VERSION_V1,
        "workload_type": "cards",
        "units": units,
        "required_materials": required_materials,
        "expected_artifacts": sorted(expected_artifacts),
        "validators": ["shape", "trace"],
        "summary_targets": summary_targets,
        "provenance_targets": provenance_targets,
    }


def build_cards_control_plane_workload_record(
    *,
    contract_payload: dict[str, Any],
    department: str,
) -> WorkloadRecord:
    return build_control_plane_workload_record_from_workload_contract(
        workload_id=CARDS_CONTROL_PLANE_WORKLOAD_ID,
        contract_payload=contract_payload,
        output_contract_ref="control_plane.contract.v1:RunRecord",
        definition_payload={"department": str(department).strip()},
    )
