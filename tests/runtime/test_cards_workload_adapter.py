from __future__ import annotations

import orket.runtime.workload_adapters as workload_adapters
from pathlib import Path

from orket.core.contracts import WORKLOAD_CONTRACT_VERSION_V1, WorkloadRecord, parse_workload_contract
from orket.application.services.control_plane_workload_catalog import (
    CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    WorkloadAuthorityInput,
    resolve_control_plane_workload,
)
from orket.runtime.workload_adapters import (
    CARDS_CONTROL_PLANE_WORKLOAD_ID,
    build_cards_workload_contract,
)
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


def test_cards_workload_adapter_does_not_export_workload_record_authority() -> None:
    assert not hasattr(workload_adapters, "build_cards_control_plane_workload_record")


def test_cards_workload_adapter_stays_raw_and_routes_authority_through_resolver(tmp_path: Path) -> None:
    contract_payload = build_cards_workload_contract(
        epic=_epic(),
        run_id="sess-2",
        build_id="build-2",
        workspace=tmp_path,
        department="core",
    )

    record = resolve_control_plane_workload(
        WorkloadAuthorityInput(
            kind="workload_contract_v1",
            workload_id=CARDS_CONTROL_PLANE_WORKLOAD_ID,
            contract_payload=contract_payload,
            output_contract_ref=CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
            definition_payload={"department": "core"},
        )
    )

    assert isinstance(record, WorkloadRecord)
    assert record.workload_id == CARDS_CONTROL_PLANE_WORKLOAD_ID
    assert record.workload_version == WORKLOAD_CONTRACT_VERSION_V1
    assert record.input_contract_ref == "docs/specs/WORKLOAD_CONTRACT_V1.md"
    assert record.output_contract_ref == CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF
    assert record.workload_digest.startswith("sha256:")
