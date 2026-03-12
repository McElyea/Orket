from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from orket.kernel.v1.canonical import canonical_json_bytes

pytestmark = pytest.mark.unit


def test_rfc8785_backend_bytes_output_is_decoded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_backend = SimpleNamespace(dumps=lambda obj: b'{"a":1,"b":2}')
    monkeypatch.setitem(sys.modules, "rfc8785", fake_backend)
    monkeypatch.delitem(sys.modules, "jcs", raising=False)

    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'
