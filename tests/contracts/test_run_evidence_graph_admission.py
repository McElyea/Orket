"""Contract admission and native publication must retain projection-only lineage."""
import asyncio
import json
from copy import deepcopy

import pytest

from orket.runtime.evidence.run_evidence_graph import (
    build_run_evidence_graph_payload,
    validate_run_evidence_graph_payload,
    write_run_evidence_graph_artifact,
)
from tests.contracts.test_run_evidence_graph_contract import _complete_payload


@pytest.mark.contract
@pytest.mark.parametrize("path,value,error", [
    (("run_evidence_graph_schema_version",), "0", "schema_version_invalid"),
    (("run_id",), "", "run_id_required"),
    (("projection_only",), False, "projection_only_invalid"),
    (("projection_only",), 1, "projection_only_invalid"),
    (("graph_result",), "success", "result_invalid"),
    (("projection_framing",), [], "projection_framing_invalid"),
    (("projection_framing", "artifact_family"), "run_graph", "projection_framing_artifact_family_invalid"),
    (("projection_framing", "scope"), "all_runs", "projection_framing_scope_invalid"),
    (("projection_framing", "lineage_rule"), "inferred", "projection_framing_lineage_rule_invalid"),
    (("generation_timestamp",), "", "generation_timestamp_required"),
    (("selected_views",), None, "selected_views_invalid"),
    (("selected_views",), [], "selected_views_invalid"),
    (("selected_views",), [""], "selected_views_invalid"),
    (("selected_views",), ["authority", "authority"], "selected_views_duplicate"),
    (("selected_views",), ["invented"], "selected_view_invalid"),
    (("source_summaries",), None, "source_summaries_invalid"),
    (("source_summaries",), [None], "source_summary_invalid"),
    (("source_summaries", 0, "source_id"), "", "source_id_required"),
    (("source_summaries", 0, "authority_level"), "inferred", "source_authority_level_invalid"),
    (("source_summaries", 0, "source_kind"), "", "source_kind_required"),
    (("source_summaries", 0, "status"), "assumed", "source_status_invalid"),
    (("issues",), None, "issues_invalid"),
    (("issues",), [None], "issue_invalid"),
    (("issues",), [{"code": "bad", "detail": ""}], "issue_contract_invalid"),
    (("issues",), [{"code": "bad", "detail": "conflict", "source_id": "missing"}], "issue_source_missing"),
    (("nodes",), None, "nodes_or_edges_invalid"),
    (("edges",), None, "nodes_or_edges_invalid"),
    (("nodes",), [None], "node_invalid"),
    (("edges",), [None], "edge_invalid"),
    (("nodes", 0, "id"), "", "node_contract_invalid"),
    (("nodes", 0, "source_ids"), [], "source_refs_invalid"),
    (("nodes", 0, "source_ids"), None, "source_refs_invalid"),
    (("nodes", 0, "source_ids"), [""], "source_refs_invalid"),
    (("nodes", 0, "source_ids"), ["src-run", "src-run"], "source_refs_duplicate"),
    (("nodes", 0, "source_ids"), ["unretained"], "source_ref_missing"),
    (("edges", 0, "id"), "", "edge_contract_invalid"),
    (("edges", 0, "source"), "missing", "edge_endpoint_missing"),
    (("edges", 0, "target"), "missing", "edge_endpoint_missing"),
    (("edges", 0, "source_ids"), [], "source_refs_invalid"),
    (("node_count",), True, "node_count_invalid"),
    (("node_count",), 0, "node_count_invalid"),
    (("edge_count",), True, "edge_count_invalid"),
    (("edge_count",), 0, "edge_count_invalid"),
])
def test_public_admission_refuses_forged_or_incomplete_projection(path, value, error):
    payload = _complete_payload()
    parent = payload
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="^run_evidence_graph_" + error + "$" ):
        validate_run_evidence_graph_payload(payload)
    assert payload == before


@pytest.mark.contract
@pytest.mark.parametrize("field,error", [("source_summaries", "source_id_duplicate"),
                                         ("nodes", "node_duplicate"), ("edges", "edge_duplicate")])
def test_duplicate_identities_cannot_alias_retained_lineage(field, error):
    payload = _complete_payload()
    payload[field].insert(0, deepcopy(payload[field][0]))
    with pytest.raises(ValueError, match="^run_evidence_graph_" + error + "$" ):
        validate_run_evidence_graph_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("field", ["source_summaries", "nodes", "edges", "issues"])
def test_uncanonical_row_order_is_refused_before_use(field):
    payload = _complete_payload()
    if field == "issues":
        payload[field] = [{"code": "z", "detail": "last"}, {"code": "a", "detail": "first"}]
    elif field == "edges":
        payload[field].append({**payload[field][0], "id": "edge:a"})
    else:
        payload[field].reverse()
    with pytest.raises(ValueError, match="run_evidence_graph_" + field + "_not_canonical"):
        validate_run_evidence_graph_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("changes,error", [
    ({"issues": [{"code": "conflict", "detail": "unresolved"}]}, "complete_issues_present"),
    ({"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}, "complete_nodes_missing"),
    ({"graph_result": "degraded"}, "degraded_basis_missing"),
    ({"graph_result": "degraded", "nodes": [], "edges": [], "node_count": 0, "edge_count": 0,
      "issues": [{"code": "missing", "detail": "no retained run"}]}, "degraded_nodes_missing"),
    ({"graph_result": "blocked"}, "blocked_artifact_shell_invalid"),
    ({"graph_result": "blocked", "nodes": [], "edges": [], "node_count": 0, "edge_count": 0},
     "blocked_reason_required"),
])
def test_outcome_claim_requires_corresponding_evidence_or_refusal_basis(changes, error):
    payload = {**_complete_payload(), **changes}
    with pytest.raises(ValueError, match="^run_evidence_graph_" + error + "$" ):
        validate_run_evidence_graph_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("status", ["missing", "contradictory", "unused"])
def test_incomplete_source_can_support_degraded_projection_but_never_complete(status):
    payload = _complete_payload()
    payload["source_summaries"][0]["status"] = status
    with pytest.raises(ValueError, match="complete_source_status_invalid"):
        validate_run_evidence_graph_payload(payload)
    payload["graph_result"] = "degraded"
    validate_run_evidence_graph_payload(payload)
    assert payload["projection_only"] is True


@pytest.mark.contract
def test_builder_normalizes_independent_metadata_without_mutating_supplied_rows():
    source = _complete_payload()
    rows = source["source_summaries"][::-1]
    rows[0].update(source_ref=" run-1 ", detail=" retained reference ")
    edge = {**source["edges"][0], "label": " final receipt "}
    before = deepcopy((rows, edge))
    result = build_run_evidence_graph_payload(run_id=" run-1 ", generation_timestamp=" time ",
        graph_result="complete", selected_views=["closure_path", "full_lineage"],
        source_summaries=rows, nodes=source["nodes"][::-1], edges=[edge])
    assert (rows, edge) == before
    assert result["run_id"] == "run-1" and result["generation_timestamp"] == "time"
    assert result["selected_views"] == ["full_lineage", "closure_path"]
    assert [row["source_id"] for row in result["source_summaries"]] == ["src-final", "src-run"]
    assert result["source_summaries"][1]["detail"] == "retained reference"
    assert result["edges"][0]["label"] == "final receipt"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refused_projection_cannot_replace_existing_native_artifact(tmp_path):
    valid = _complete_payload()
    path = await write_run_evidence_graph_artifact(root=tmp_path, session_id="selected", payload=valid)
    before = await asyncio.to_thread(path.read_bytes)
    assert json.loads(before) == valid
    invalid = {**valid, "projection_only": False}
    with pytest.raises(ValueError, match="projection_only_invalid"):
        await write_run_evidence_graph_artifact(root=tmp_path, session_id="selected", payload=invalid)
    assert await asyncio.to_thread(path.read_bytes) == before
    with pytest.raises(ValueError, match="projection_only_invalid"):
        await write_run_evidence_graph_artifact(root=tmp_path, session_id="unpublished", payload=invalid)
    assert not await asyncio.to_thread((tmp_path / "runs/unpublished").exists)
