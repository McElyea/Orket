"""Summary projection contracts; retained fact labels do not prove their effects."""
from copy import deepcopy

import pytest

from orket.runtime.summary.run_summary_packet2 import build_packet2_extension, normalize_packet2_facts

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("section,container", [
    ("narration_to_effect_audit", "entries"), ("idempotency", "surfaces"),
])
@pytest.mark.parametrize("rows", ["invalid", [None], [{}]])
def test_incomplete_effect_facts_do_not_create_summary_authority(section, container, rows):
    facts = {section: {container: rows}}
    before = deepcopy(facts)
    assert normalize_packet2_facts(facts) == {}
    assert build_packet2_extension(artifacts={"packet2_facts": facts}) is None
    assert facts == before


@pytest.mark.parametrize("index,expected", [(True, 0), ("bad", 0), ("2", 2), (-1, 0)])
def test_repair_deduplication_preserves_reasons_and_material_change(index, expected):
    facts = {"repair_entries": [None, {}, {"repair_id": "same", "turn_index": index,
        "reasons": ["first"], "material_change": False},
        {"repair_id": "same", "reasons": ["second", "first"], "material_change": True}]}
    before = deepcopy(facts)
    projection = build_packet2_extension(artifacts={"packet2_facts": facts})
    assert projection["projection_only"] is True and projection["projection_source"] == "packet2_facts"
    ledger = projection["repair_ledger"]
    assert ledger["repair_count"] == 1 and ledger["final_disposition"] == "accepted_with_repair"
    assert ledger["entries"] == [{"repair_id": "same", "turn_index": expected,
        "source_event": "turn_corrective_reprompt", "strategy": "corrective_reprompt",
        "reasons": ["first", "second"], "material_change": True}]
    assert facts == before


def test_invalid_repair_disposition_refuses_projection_without_mutating_facts():
    facts = {"repair_entries": [{"repair_id": "repair"}], "final_disposition": "invented"}
    before = deepcopy(facts)
    with pytest.raises(ValueError, match="packet2_final_disposition_invalid"):
        build_packet2_extension(artifacts={"packet2_facts": facts})
    assert facts == before


@pytest.mark.parametrize("rows", [None, [None, {}]])
def test_source_attribution_excludes_incomplete_claims_and_sources(rows):
    facts = {"source_attribution": {"mode": "required", "synthesis_status": "blocked",
        "claims": rows, "sources": rows, "missing_requirements": ["sources", " ", "sources"]}}
    before = deepcopy(facts)
    projection = build_packet2_extension(artifacts={"packet2_facts": facts})
    source = projection["source_attribution"]
    assert source["claim_count"] == source["source_count"] == 0
    assert "claims" not in source and "sources" not in source
    assert source["missing_requirements"] == ["sources"]
    assert source["synthesis_status"] == "blocked" and not source["artifact_provenance_verified"]
    assert projection["projection_only"] and facts == before


def test_invalid_source_status_cannot_create_an_attribution_section():
    facts = {"source_attribution": {"mode": "required", "synthesis_status": "pretend_verified"}}
    assert build_packet2_extension(artifacts={"packet2_facts": facts}) is None


def test_distinct_idempotency_surfaces_preserve_count_and_control_plane_references():
    facts = {"idempotency": {"surfaces": [
        {"surface": "write_file", "operation_id": "a", "tool": "write_file", "target": "a.txt",
         "dedupe_status": "single_delivery", "turn_index": "3", "control_plane_run_id": "run"},
        {"surface": "write_file", "operation_id": "b", "tool": "write_file", "target": "b.txt",
         "dedupe_status": "reused"},
    ]}}
    projected = build_packet2_extension(artifacts={"packet2_facts": facts})
    assert projected["idempotency"]["observed_surface_count"] == 2
    assert projected["idempotency"]["duplicate_operation_count"] == 1
    assert projected["idempotency"]["surfaces"][0]["turn_index"] == 3
    assert projected["idempotency"]["surfaces"][0]["control_plane_run_id"] == "run"
