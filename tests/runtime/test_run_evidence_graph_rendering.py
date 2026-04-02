from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.run_evidence_graph_projection import project_run_evidence_graph_primary_lineage
from orket.runtime.run_evidence_graph_rendering import (
    build_run_evidence_graph_html,
    build_run_evidence_graph_mermaid,
    build_run_evidence_graph_views,
    write_run_evidence_graph_rendered_artifacts,
)
from tests.runtime.run_evidence_graph_test_support import (
    GENERATED_AT,
    seed_complete_primary_lineage_in_memory,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "run_evidence_graph"


# Layer: integration
@pytest.mark.asyncio
async def test_build_run_evidence_graph_views_derives_required_filtered_views_from_one_payload(
    tmp_path: Path,
) -> None:
    execution_repo, record_repo, session_id, run_id = await seed_complete_primary_lineage_in_memory(
        tmp_path=tmp_path
    )
    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
        selected_views=[
            "decision",
            "closure_path",
            "resource_authority_path",
            "authority",
            "failure_path",
            "full_lineage",
        ],
    )

    views = build_run_evidence_graph_views(payload)
    view_by_name = {view["view"]: view for view in views}

    assert [view["view"] for view in views] == [
        "full_lineage",
        "failure_path",
        "authority",
        "decision",
        "resource_authority_path",
        "closure_path",
    ]
    assert views[0]["node_count"] == payload["node_count"]
    assert views[0]["edge_count"] == payload["edge_count"]
    assert {node["family"] for node in view_by_name["failure_path"]["nodes"]} >= {
        "run",
        "attempt",
        "step",
        "checkpoint",
        "checkpoint_acceptance",
        "recovery_decision",
        "final_truth",
    }
    assert "reservation" not in {node["family"] for node in view_by_name["failure_path"]["nodes"]}
    assert {node["family"] for node in view_by_name["authority"]["nodes"]} >= {
        "run",
        "attempt",
        "step",
        "reservation",
        "lease",
        "resource",
        "observation",
        "effect",
        "operator_action",
        "final_truth",
    }
    assert "checkpoint" not in {node["family"] for node in view_by_name["authority"]["nodes"]}
    assert "checkpoint_acceptance" not in {
        node["family"] for node in view_by_name["authority"]["nodes"]
    }
    assert "recovery_decision" not in {node["family"] for node in view_by_name["authority"]["nodes"]}
    assert {node["family"] for node in view_by_name["decision"]["nodes"]} >= {
        "run",
        "attempt",
        "step",
        "checkpoint",
        "checkpoint_acceptance",
        "recovery_decision",
        "observation",
        "operator_action",
        "final_truth",
    }
    assert "reservation" not in {node["family"] for node in view_by_name["decision"]["nodes"]}
    assert "lease" not in {node["family"] for node in view_by_name["decision"]["nodes"]}
    assert "resource" not in {node["family"] for node in view_by_name["decision"]["nodes"]}
    assert {node["family"] for node in view_by_name["resource_authority_path"]["nodes"]} >= {
        "run",
        "attempt",
        "step",
        "reservation",
        "lease",
        "resource",
        "observation",
        "effect",
        "operator_action",
        "final_truth",
    }
    assert "checkpoint" not in {
        node["family"] for node in view_by_name["resource_authority_path"]["nodes"]
    }
    assert {node["family"] for node in view_by_name["closure_path"]["nodes"]} >= {
        "run",
        "attempt",
        "step",
        "observation",
        "effect",
        "recovery_decision",
        "operator_action",
        "final_truth",
    }
    assert "reservation" not in {node["family"] for node in view_by_name["closure_path"]["nodes"]}


# Layer: integration
@pytest.mark.asyncio
async def test_write_run_evidence_graph_rendered_artifacts_writes_mermaid_and_html(
    tmp_path: Path,
) -> None:
    execution_repo, record_repo, session_id, run_id = await seed_complete_primary_lineage_in_memory(
        tmp_path=tmp_path
    )
    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
        selected_views=["full_lineage", "authority", "decision"],
    )

    paths = await write_run_evidence_graph_rendered_artifacts(
        root=tmp_path,
        session_id=session_id,
        payload=payload,
    )
    mermaid = build_run_evidence_graph_mermaid(payload)
    html = build_run_evidence_graph_html(payload)

    assert paths["mermaid_path"] == tmp_path / "runs" / session_id / "run_evidence_graph.mmd"
    assert paths["html_path"] == tmp_path / "runs" / session_id / "run_evidence_graph.html"
    assert paths["mermaid_path"].read_text(encoding="utf-8") == mermaid
    assert paths["html_path"].read_text(encoding="utf-8") == html
    assert mermaid.startswith("flowchart TD\n")
    assert 'subgraph view_full_lineage["Full Lineage | ' in mermaid
    assert 'subgraph view_authority["Authority | ' in mermaid
    assert 'subgraph view_decision["Decision | ' in mermaid
    assert "attempt_to_recovery_decision" in mermaid
    assert "<h1>Run Evidence Graph</h1>" in html
    assert "Authority" in html
    assert "Decision" in html
    assert "events.log" in html


# Layer: integration
@pytest.mark.asyncio
async def test_build_run_evidence_graph_mermaid_matches_showcase_snapshot(
    tmp_path: Path,
) -> None:
    execution_repo, record_repo, session_id, run_id = await seed_complete_primary_lineage_in_memory(
        tmp_path=tmp_path
    )
    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
        selected_views=["full_lineage", "failure_path", "resource_authority_path", "closure_path"],
    )

    mermaid = build_run_evidence_graph_mermaid(payload)
    fixture_path = FIXTURES_ROOT / "complete_primary_lineage.mmd"

    assert mermaid == fixture_path.read_text(encoding="utf-8")
