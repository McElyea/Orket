from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.runtime.run_evidence_graph import (
    build_blocked_run_evidence_graph_payload,
    build_run_evidence_graph_payload,
    validate_run_evidence_graph_payload,
    write_run_evidence_graph_artifact,
)

_GENERATED_AT = "2036-03-05T12:00:05+00:00"


def _complete_payload() -> dict[str, object]:
    return build_run_evidence_graph_payload(
        run_id="cards-epic-run:sess-graph-runtime:build-1:20360305T120000000000Z",
        generation_timestamp=_GENERATED_AT,
        graph_result="complete",
        selected_views=["resource_authority_path", "full_lineage"],
        source_summaries=[
            {
                "source_id": "src-lease",
                "authority_level": "primary",
                "source_kind": "LeaseRecord",
                "status": "present",
                "source_ref": "lease-1",
            },
            {
                "source_id": "src-resource",
                "authority_level": "primary",
                "source_kind": "ResourceRecord",
                "status": "present",
                "source_ref": "resource-1",
            },
        ],
        nodes=[
            {
                "id": "lease:lease-1",
                "family": "lease",
                "label": "lease-1",
                "source_ids": ["src-lease"],
            },
            {
                "id": "resource:resource-1",
                "family": "resource",
                "label": "resource-1",
                "source_ids": ["src-resource"],
            },
        ],
        edges=[
            {
                "id": "edge:lease-to-resource",
                "family": "lease_to_resource_authority",
                "source": "lease:lease-1",
                "target": "resource:resource-1",
                "source_ids": ["src-lease", "src-resource"],
            }
        ],
    )


# Layer: contract
def test_build_blocked_run_evidence_graph_payload_emits_blocked_artifact_shell() -> None:
    payload = build_blocked_run_evidence_graph_payload(
        run_id="cards-epic-run:sess-graph-blocked:build-1:20360305T120000000000Z",
        generation_timestamp=_GENERATED_AT,
        selected_views=["failure_path", "full_lineage"],
        issues=[
            {
                "code": "run_not_v1_covered",
                "detail": "selected run does not satisfy the V1 covered-run gate",
            }
        ],
    )

    validate_run_evidence_graph_payload(payload)

    assert payload["graph_result"] == "blocked"
    assert payload["selected_views"] == ["full_lineage", "failure_path"]
    assert payload["node_count"] == 0
    assert payload["edge_count"] == 0
    assert payload["nodes"] == []
    assert payload["edges"] == []


# Layer: contract
def test_validate_run_evidence_graph_payload_rejects_noncanonical_view_order() -> None:
    payload = _complete_payload()
    payload["selected_views"] = ["resource_authority_path", "full_lineage"]

    with pytest.raises(ValueError, match="run_evidence_graph_selected_views_not_canonical"):
        validate_run_evidence_graph_payload(payload)


# Layer: contract
def test_build_run_evidence_graph_payload_canonicalizes_authority_and_decision_view_order() -> None:
    payload = build_run_evidence_graph_payload(
        run_id="cards-epic-run:sess-graph-runtime:build-2:20360305T120000000000Z",
        generation_timestamp=_GENERATED_AT,
        graph_result="complete",
        selected_views=["decision", "full_lineage", "authority"],
        source_summaries=[
            {
                "source_id": "src-run",
                "authority_level": "primary",
                "source_kind": "RunRecord",
                "status": "present",
                "source_ref": "run-1",
            }
        ],
        nodes=[
            {
                "id": "run:run-1",
                "family": "run",
                "label": "run-1",
                "source_ids": ["src-run"],
            }
        ],
        edges=[],
    )

    assert payload["selected_views"] == ["full_lineage", "authority", "decision"]


# Layer: integration
@pytest.mark.asyncio
async def test_write_run_evidence_graph_artifact_writes_canonical_json(tmp_path: Path) -> None:
    payload = _complete_payload()

    graph_path = await write_run_evidence_graph_artifact(
        root=tmp_path,
        session_id="sess-graph-runtime",
        payload=payload,
    )

    assert graph_path == tmp_path / "runs" / "sess-graph-runtime" / "run_evidence_graph.json"
    assert json.loads(graph_path.read_bytes().decode("utf-8")) == payload
