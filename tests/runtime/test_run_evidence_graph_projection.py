from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.run_evidence_graph_projection import project_run_evidence_graph_primary_lineage
from tests.runtime.run_evidence_graph_test_support import (
    GENERATED_AT,
    seed_complete_primary_lineage_in_memory,
)


# Layer: integration
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_emits_complete_deterministic_graph(
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
        selected_views=["resource_authority_path", "full_lineage", "closure_path"],
    )
    replay = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
        selected_views=["closure_path", "full_lineage", "resource_authority_path"],
    )

    assert payload == replay
    assert payload["graph_result"] == "complete"
    assert payload["selected_views"] == ["full_lineage", "resource_authority_path", "closure_path"]
    assert payload["node_count"] == len(payload["nodes"])
    assert payload["edge_count"] == len(payload["edges"])
    assert {node["family"] for node in payload["nodes"]} >= {
        "run",
        "attempt",
        "step",
        "checkpoint",
        "checkpoint_acceptance",
        "recovery_decision",
        "reservation",
        "lease",
        "resource",
        "observation",
        "effect",
        "operator_action",
        "final_truth",
    }
    assert any(
        node["family"] == "observation" and node["attributes"]["observation_kind"] == "effect_observed_result"
        for node in payload["nodes"]
    )
    assert any(
        node["family"] == "observation" and node["attributes"]["observation_kind"] == "resource_current_state"
        for node in payload["nodes"]
    )
    assert any(
        node["family"] == "observation"
        and node["attributes"]["observation_kind"] == "final_truth_authoritative_result"
        for node in payload["nodes"]
    )
    assert any(edge["family"] == "reservation_to_lease_promotion" for edge in payload["edges"])
    assert any(edge["family"] == "lease_to_resource_authority" for edge in payload["edges"])
    assert any(edge["family"] == "attempt_to_recovery_decision" for edge in payload["edges"])
    assert any(edge["family"] == "attempt_to_checkpoint" for edge in payload["edges"])
    assert any(edge["family"] == "checkpoint_to_checkpoint_acceptance" for edge in payload["edges"])
    assert any(edge["family"] == "step_to_observation" for edge in payload["edges"])
    assert any(edge["family"] == "observation_to_effect" for edge in payload["edges"])
    assert any(edge["family"] == "observation_to_resource" for edge in payload["edges"])
    assert any(edge["family"] == "observation_to_final_truth" for edge in payload["edges"])
    assert any(edge["family"] == "operator_action_to_affected_resource" for edge in payload["edges"])
    assert any(edge["family"] == "final_truth_to_run" for edge in payload["edges"])
    assert all(summary["status"] == "present" for summary in payload["source_summaries"])
    assert any(summary["source_kind"] == "events.log" for summary in payload["source_summaries"])
    assert any(summary["source_kind"] == "run_ledger.summary_json" for summary in payload["source_summaries"])
    assert any(summary["source_kind"] == "run_summary.json" for summary in payload["source_summaries"])
    run_node = next(node for node in payload["nodes"] if node["family"] == "run")
    assert run_node["attributes"]["supplemental_run_summary_ref"] == f"runs/{session_id}/run_summary.json"
    assert run_node["attributes"]["supplemental_run_ledger_summary_ref"] == (
        f"runs/{session_id}/events.log#get_run.summary_json"
    )
    assert run_node["attributes"]["supplemental_run_ledger_started_event_seq"] == 1
    assert run_node["attributes"]["supplemental_run_ledger_ended_event_seq"] == 6
    assert run_node["attributes"]["supplemental_runtime_events_ref"] == f"runs/{session_id}/events.log"
    attempt_two = next(node for node in payload["nodes"] if node["id"] == f"attempt:{run_id}:attempt:0002")
    checkpoint_step = next(node for node in payload["nodes"] if node["id"] == f"step:{run_id}:step:checkpoint")
    commit_step = next(node for node in payload["nodes"] if node["id"] == f"step:{run_id}:step:commit")
    assert attempt_two["attributes"]["supplemental_run_ledger_selected_attempt"] is True
    assert checkpoint_step["attributes"]["supplemental_runtime_event_seq_range"] == [2, 3]
    assert checkpoint_step["attributes"]["supplemental_runtime_order_index"] == 1
    assert commit_step["attributes"]["supplemental_runtime_event_seq_range"] == [4, 5]
    assert commit_step["attributes"]["supplemental_runtime_order_index"] == 2
    assert commit_step["attributes"]["supplemental_run_ledger_selected_step"] is True
