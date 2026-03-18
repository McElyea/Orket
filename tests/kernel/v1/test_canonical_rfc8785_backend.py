from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from orket.kernel.v1.canon import canonical_bytes as odr_canonical_bytes
from orket.kernel.v1.canonical import canonical_json_bytes

pytestmark = pytest.mark.unit


def test_rfc8785_backend_bytes_output_is_decoded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_backend = SimpleNamespace(dumps=lambda obj: b'{"a":1,"b":2}')
    monkeypatch.setitem(sys.modules, "rfc8785", fake_backend)
    monkeypatch.delitem(sys.modules, "jcs", raising=False)

    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_odr_and_rfc8785_canonicalizers_remain_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_backend = SimpleNamespace(
        dumps=lambda obj: json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    monkeypatch.setitem(sys.modules, "rfc8785", fake_backend)
    monkeypatch.delitem(sys.modules, "jcs", raising=False)

    payload = {
        "timestamp": "2026-03-17T00:00:00Z",
        "nodes": [{"id": "b"}, {"id": "a"}],
    }

    assert odr_canonical_bytes(payload) != canonical_json_bytes(payload)
