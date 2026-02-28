from __future__ import annotations

from pathlib import Path

from orket.core.contracts import WORKLOAD_CONTRACT_VERSION_V1, parse_workload_contract
from orket.runtime.workload_adapters import build_cards_workload_contract
from orket.schema import ArchitectureGovernance, EpicConfig, IssueConfig


def _epic() -> EpicConfig:
    return EpicConfig(
        id="epic-1",
        name="epic-1",
        type="epic",
        team="standard",
        environment="standard",
        description="adapter test",
        architecture_governance=ArchitectureGovernance(idesign=False, pattern="Standard"),
        issues=[
            IssueConfig(id="ISSUE-1", summary="A", seat="lead_architect", priority="High", depends_on=[]),
            IssueConfig(id="ISSUE-2", summary="B", seat="lead_architect", priority="Medium", depends_on=["ISSUE-1"]),
        ],
    )


def test_build_cards_workload_contract_v1_shape(tmp_path: Path) -> None:
    payload = build_cards_workload_contract(
        epic=_epic(),
        run_id="sess-1",
        build_id="build-1",
        workspace=tmp_path,
        department="core",
    )
    model = parse_workload_contract(payload)
    assert model.workload_contract_version == WORKLOAD_CONTRACT_VERSION_V1
    assert model.workload_type == "cards"
    assert len(model.units) == 2
    assert any(unit.get("card_id") == "ISSUE-1" for unit in model.units)
    assert any(item.get("kind") == "asset" for item in model.required_materials)
