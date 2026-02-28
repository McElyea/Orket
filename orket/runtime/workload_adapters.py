from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.core.contracts import WORKLOAD_CONTRACT_VERSION_V1
from orket.schema import EpicConfig


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
