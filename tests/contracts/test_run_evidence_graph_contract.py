# Layer: contract

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from orket.runtime.run_evidence_graph import (
    build_run_evidence_graph_payload,
    validate_run_evidence_graph_payload,
)

pytestmark = pytest.mark.contract

_GENERATED_AT = "2036-03-05T12:00:05+00:00"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes().decode("utf-8"))


def _complete_payload() -> dict[str, object]:
    return build_run_evidence_graph_payload(
        run_id="cards-epic-run:sess-graph-contract:build-1:20360305T120000000000Z",
        generation_timestamp=_GENERATED_AT,
        graph_result="complete",
        selected_views=["closure_path", "full_lineage"],
        source_summaries=[
            {
                "source_id": "src-final",
                "authority_level": "primary",
                "source_kind": "FinalTruthRecord",
                "status": "present",
                "source_ref": "truth-1",
            },
            {
                "source_id": "src-run",
                "authority_level": "primary",
                "source_kind": "RunRecord",
                "status": "present",
                "source_ref": "run-1",
            },
        ],
        nodes=[
            {
                "id": "run:run-1",
                "family": "run",
                "label": "run-1",
                "source_ids": ["src-run"],
            },
            {
                "id": "truth:truth-1",
                "family": "final_truth",
                "label": "truth-1",
                "source_ids": ["src-final"],
            },
        ],
        edges=[
            {
                "id": "edge:truth-to-run",
                "family": "final_truth_to_run",
                "source": "truth:truth-1",
                "target": "run:run-1",
                "source_ids": ["src-final"],
            }
        ],
    )


def test_run_evidence_graph_schema_and_registry_pin_a_separate_artifact_family() -> None:
    payload = _complete_payload()
    validate_run_evidence_graph_payload(payload)

    schema = _read_json(Path("core/artifacts/run_evidence_graph_schema.json"))
    registry = yaml.safe_load(Path("core/artifacts/schema_registry.yaml").read_bytes().decode("utf-8"))

    Draft202012Validator(schema).validate(payload)

    assert schema["required"] == [
        "run_evidence_graph_schema_version",
        "run_id",
        "projection_only",
        "graph_result",
        "projection_framing",
        "generation_timestamp",
        "selected_views",
        "source_summaries",
        "issues",
        "node_count",
        "edge_count",
        "nodes",
        "edges",
    ]
    assert schema["properties"]["selected_views"]["items"]["enum"] == [
        "full_lineage",
        "failure_path",
        "authority",
        "decision",
        "resource_authority_path",
        "closure_path",
    ]
    assert registry["artifacts"]["run_evidence_graph.json"] == "1.0"
    assert registry["artifacts"]["run_graph.json"] == "1.0"


def test_run_evidence_graph_contract_rejects_legacy_run_graph_vocabulary() -> None:
    payload = _complete_payload()
    payload["nodes"][0]["family"] = "tool_call"

    with pytest.raises(ValueError, match="run_evidence_graph_node_contract_invalid"):
        validate_run_evidence_graph_payload(payload)

    payload = _complete_payload()
    payload["edges"][0]["family"] = "artifact_produced"

    with pytest.raises(ValueError, match="run_evidence_graph_edge_contract_invalid"):
        validate_run_evidence_graph_payload(payload)


def test_run_evidence_graph_contract_accepts_attempt_checkpoint_edge_family() -> None:
    payload = build_run_evidence_graph_payload(
        run_id="kernel-action-run:sess-graph-contract:trace-1",
        generation_timestamp=_GENERATED_AT,
        graph_result="complete",
        selected_views=["failure_path"],
        source_summaries=[
            {
                "source_id": "src-attempt",
                "authority_level": "primary",
                "source_kind": "AttemptRecord",
                "status": "present",
                "source_ref": "attempt-1",
            },
            {
                "source_id": "src-checkpoint",
                "authority_level": "primary",
                "source_kind": "CheckpointRecord",
                "status": "present",
                "source_ref": "checkpoint-1",
            },
        ],
        nodes=[
            {
                "id": "attempt:attempt-1",
                "family": "attempt",
                "label": "attempt-1",
                "source_ids": ["src-attempt"],
            },
            {
                "id": "checkpoint:checkpoint-1",
                "family": "checkpoint",
                "label": "checkpoint-1",
                "source_ids": ["src-checkpoint"],
            },
        ],
        edges=[
            {
                "id": "edge:attempt-to-checkpoint",
                "family": "attempt_to_checkpoint",
                "source": "attempt:attempt-1",
                "target": "checkpoint:checkpoint-1",
                "source_ids": ["src-attempt", "src-checkpoint"],
            }
        ],
    )

    validate_run_evidence_graph_payload(payload)
