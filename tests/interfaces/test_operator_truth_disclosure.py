"""Layer: contract. Retained repair warnings must survive operator projection."""
from copy import deepcopy

import pytest

from orket.interfaces.operator_view_models import build_run_detail_view, build_run_history_item_view

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("build", [build_run_detail_view, build_run_history_item_view])
def test_repaired_accepted_run_discloses_defect_without_changing_retained_truth(build):
    packet = {"provenance": {"repair_occurred": True, "truth_classification": "repaired"},
              "classification": {"classification_applicable": True, "truth_classification": "repaired"},
              "defects": {"defects_present": True, "defect_families": ["silent_repaired_success"]},
              "packet1_conformance": {"status": "non_conformant", "reasons": ["silent_repaired_success"]}}
    summary = {"truthful_runtime_packet1": deepcopy(packet)}
    view = build(session_id="retained", status="done", summary=summary, artifacts={},
                 completion={"completion_accepted": True, "completion_rejection": None})
    assert view["completion_accepted"] and view["primary_status"] == "completed" and not view["degraded"]
    assert "required repair" in view["summary"] and "nonconformance" in view["summary"]
    assert view["runtime_truth"]["packet1_conformance"] == packet["packet1_conformance"]
    assert {"run.truth.repaired", "run.truth.non_conformant"}.issubset(view["reason_codes"])
    assert summary == {"truthful_runtime_packet1": packet}


def test_missing_packet_does_not_imply_conformance():
    view = build_run_detail_view(session_id="historical", status="done", summary={}, artifacts={},
                                completion={"completion_accepted": False, "completion_rejection": "E_UNVERIFIED"})
    assert view["runtime_truth"] == {"available": False}
    assert "declared acceptance is unverified" in view["summary"]
