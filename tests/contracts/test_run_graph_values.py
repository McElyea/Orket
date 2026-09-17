"""Pure graph projection captures JSON inputs without consulting effect capabilities."""
from copy import deepcopy
from itertools import permutations

import pytest

from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError
from orket.core.contracts.run_graph import reconstruct_run_graph

pytestmark = pytest.mark.contract


def events():
    return [
        {"event_seq": 1, "kind": "run_started", "run_id": "run", "artifacts": {"input": {"values": [1, 2]}}},
        {"event_seq": 2, "kind": "tool_call", "run_id": "run", "step_id": "step", "operation_id": "op"},
        {"event_seq": 3, "kind": "operation_result", "call_sequence_number": 2,
         "result": {"ok": True, "compat_translation": {"mapping_version": {"major": 1}}}},
        {"event_seq": 4, "kind": "run_finalized", "run_id": "run", "artifacts": {"summary": {"status": "incomplete"}}},
    ]


def test_projection_has_identical_values_for_every_event_order_and_keeps_inputs_unchanged():
    """Layer: contract. All 24 event permutations preserve the same graph and digest."""
    source = events()
    before = deepcopy(source)
    expected = reconstruct_run_graph(source)
    for order in permutations(source):
        assert reconstruct_run_graph(list(order)) == expected
    assert source == before


def test_projection_does_not_borrow_nested_input_or_previous_output_values():
    """Layer: contract. Mutating one result cannot alter the source or a future result."""
    source = events()
    expected = reconstruct_run_graph(source)
    changed = reconstruct_run_graph(source)
    node = next(row for row in changed["nodes"] if row["type"] == "compat_mapping")
    node["mapping_version"]["major"] = 999
    assert reconstruct_run_graph(source) == expected
    assert source[2]["result"]["compat_translation"]["mapping_version"] == {"major": 1}


def test_non_json_artifact_cannot_invoke_an_effectful_string_fallback():
    """Layer: contract. Unsupported values refuse without invoking user-defined conversion."""
    class Effectful:
        def __str__(self):
            raise AssertionError("object conversion was invoked")

    source = events()
    source[0]["artifacts"]["input"] = Effectful()
    with pytest.raises(ProtocolCanonicalizationError, match="Unsupported canonical JSON value"):
        reconstruct_run_graph(source)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_cannot_enter_a_graph_digest(value):
    """Layer: contract. Non-finite inputs refuse before a derived graph is emitted."""
    source = events()
    source[0]["artifacts"]["input"] = value
    with pytest.raises(ProtocolCanonicalizationError, match="Non-finite"):
        reconstruct_run_graph(source)
