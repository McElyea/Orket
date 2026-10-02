"""Offline consistency of native exports does not establish retained truth or authenticity."""
import asyncio
from copy import deepcopy

import pytest
import pytest_asyncio

from orket.core.domain.outward_ledger import verify_ledger_export
from tests.helpers.outward_ledger import logical_contents, seed_ledger

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def exported(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 4)
    payload = await service.export("bt2")
    before = await asyncio.to_thread(logical_contents, path)
    assert verify_ledger_export(payload)["result"] == "valid"
    yield payload
    assert await asyncio.to_thread(logical_contents, path) == before


def _verify(payload, expected):
    before = deepcopy(payload)
    result = verify_ledger_export(payload)
    assert payload == before
    assert result["result"] == "invalid" and any(expected in item for item in result["errors"]), result
    assert result["verification_scope"] == "export_self_consistency"
    assert result["retained_integrity"] == result["snapshot_completeness"] == "not_verified"
    assert result["authenticity"] == "not_established"


@pytest.mark.parametrize("field,value,error", [
    ("schema_version", "other", "schema_version must"), ("run_id", " ", "run_id must"),
    ("export_scope", "unknown", "export_scope must"), ("canonical", [], "canonical must be an object"),
    ("events", {}, "events must be an array"),
])
async def test_export_envelope_refusal_preserves_native_ledger(exported, field, value, error):
    exported[field] = value
    _verify(exported, error)


async def test_nonobject_export_is_explicitly_invalid(exported):
    _verify([], "ledger export must be an object")
    assert verify_ledger_export(exported)["result"] == "valid"


@pytest.mark.parametrize("field,value,error", [
    ("event_count", True, "event_count must be an integer"),
    ("event_count", -1, "ledger event count exceeds supported bounds"),
    ("event_count", 100001, "ledger event count exceeds supported bounds"),
    ("event_count", 3, "full export event count does not match"),
    ("ledger_hash", "", "canonical.ledger_hash is required"),
    ("ledger_hash", "incorrect", "full export final chain_hash"),
    ("genesis", "incorrect", "canonical.genesis must be GENESIS"),
    ("ordering", ["event_id"], "canonical.ordering must preserve"),
])
async def test_canonical_claims_cannot_override_export_evidence(exported, field, value, error):
    exported["canonical"][field] = value
    _verify(exported, error)


@pytest.mark.parametrize("field,value,error", [
    ("position", "1", "position must be an integer"),
    ("event_id", "", "event_id must be a nonempty string"),
    ("event_type", 1, "event_type must be a nonempty string"),
    ("run_id", "other", "event identity mismatch"),
    ("turn", True, "turn must be an integer or null"),
    ("payload", [], "payload must be an object"),
    ("previous_chain_hash", "incorrect", "previous_chain_hash mismatch"),
])
async def test_event_admission_keeps_field_and_identity_diagnostics(exported, field, value, error):
    exported["events"][0][field] = value
    _verify(exported, error)


async def test_nonobject_event_and_missing_sequence_are_not_silently_removed(exported):
    nonobject = deepcopy(exported)
    nonobject["events"].insert(0, [])
    _verify(nonobject, "event entry must be an object")
    exported["events"].pop(1)
    _verify(exported, "full export missing position 2")


def _partial(full):
    # A disclosed projection of the actual export; hashes remain exactly as exported.
    payload = deepcopy(full)
    events = full["events"]
    payload.update(export_scope="partial_view", events=[deepcopy(events[0]), deepcopy(events[3])],
        omitted_spans=[dict(from_position=2, to_position=3,
            previous_chain_hash=events[0]["chain_hash"], next_chain_hash=events[2]["chain_hash"])])
    assert verify_ledger_export(payload)["result"] == "partial_valid"
    return payload


@pytest.mark.parametrize("case,error", [
    ("missing", "omitted_spans must be an array"), ("nonobject", "omitted span must be an object"),
    ("inverted", "is inverted"), ("outside", "outside canonical event_count"),
    ("disclosed", "overlaps disclosed events"), ("duplicate", "overlaps another span"),
    ("previous", "previous anchor mismatch"), ("next", "next anchor mismatch"),
    ("uncovered", "do not cover exactly"), ("count", "disclosed event position exceeds"),
])
async def test_partial_disclosure_cannot_hide_invalid_span_claims(exported, case, error):
    partial = _partial(exported)
    span = partial["omitted_spans"][0]
    if case == "missing":
        partial.pop("omitted_spans")
    elif case == "nonobject":
        partial["omitted_spans"] = [None]
    elif case == "inverted":
        span.update(from_position=3, to_position=2)
    elif case == "outside":
        span["from_position"] = 0
    elif case == "disclosed":
        span["from_position"] = 1
    elif case == "duplicate":
        partial["omitted_spans"].append(deepcopy(span))
    elif case == "previous":
        span["previous_chain_hash"] = "incorrect"
    elif case == "next":
        span["next_chain_hash"] = "incorrect"
    elif case == "uncovered":
        partial["omitted_spans"] = []
    elif case == "count":
        partial["canonical"]["event_count"] = 3
    _verify(partial, error)


async def test_partial_tail_and_adjacent_disclosure_must_preserve_chain_anchors(exported):
    tail = deepcopy(exported)
    tail.update(export_scope="partial_view", events=[], omitted_spans=[dict(from_position=1, to_position=4,
        previous_chain_hash="GENESIS", next_chain_hash=exported["canonical"]["ledger_hash"])])
    assert verify_ledger_export(tail)["result"] == "partial_valid"
    tail["omitted_spans"][0]["next_chain_hash"] = "incorrect"
    _verify(tail, "does not anchor canonical ledger_hash")
    adjacent = deepcopy(exported)
    adjacent.update(export_scope="partial_view", omitted_spans=[])
    adjacent["events"][1]["previous_chain_hash"] = "incorrect"
    _verify(adjacent, "disclosed chain link mismatch")


async def test_empty_export_requires_genesis_instead_of_unobserved_final_hash(exported):
    exported["events"] = []
    exported["canonical"]["event_count"] = 0
    _verify(exported, "empty ledger_hash must be GENESIS")
