"""Layer: contract. Immutable byte inputs determine every staging value."""

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from orket.application.services.kernel_triplet_input_service import capture_kernel_triplet
from orket.core.contracts.kernel_triplet import KernelTripletInputs, plan_kernel_triplet

pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_equal_captured_triplets_have_equal_pure_plans(tmp_path, monkeypatch):
    first = capture_kernel_triplet(
        {"id": "one", "dto_type": "ITEM"},
        {
            "a/b~": [
                {"type": "item", "id": "one", "relationship": "uses"},
            ]
        },
        {},
    )
    second = capture_kernel_triplet(
        {"dto_type": "ITEM", "id": "one"},
        {
            "a/b~": [
                {"relationship": "uses", "id": "one", "type": "item"},
            ]
        },
        {},
    )
    monkeypatch.setattr("pathlib.Path.cwd", lambda: pytest.fail("pure plan sampled cwd"))
    left, right = [plan_kernel_triplet(value, stem="data/item") for value in (first, second)]
    assert first == second and left == right
    assert left.digests.dto_type == "item"
    assert left.references[0][2].location == "/links/a~1b~0/0"
    assert left.references[0][2].artifact_digest == left.digests.links_digest
    assert left.objects[0] == (left.digests.body_digest, first.body)
    with pytest.raises(FrozenInstanceError):
        left.references[0][2].stem = "changed"
    with pytest.raises(FrozenInstanceError):
        first.links = b"{}"
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []


@pytest.mark.parametrize("value", [None, {}, b"[]", b"null", b"{broken"])
def test_invalid_triplet_object_bytes_refuse(value):
    with pytest.raises(ValueError):
        KernelTripletInputs(value, b"{}", b"{}")


def test_request_capture_detaches_nested_values_and_keeps_number_profile():
    body = {"nested": {"values": [1, 2]}}
    captured = capture_kernel_triplet(body, {}, {})
    before = plan_kernel_triplet(captured, stem="item")
    body["nested"]["values"].append(3)
    assert plan_kernel_triplet(captured, stem="item") == before
    assert b"[1,2]" in captured.body and b"[1,2,3]" not in captured.body
    with pytest.raises(ValueError, match="float"):
        capture_kernel_triplet({"value": 0.5}, {}, {})
