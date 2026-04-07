from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.kernel.v1.canonical import canonical_json_bytes, odr_canonical_json_bytes

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

    assert odr_canonical_json_bytes(payload) != canonical_json_bytes(payload)


def test_no_source_imports_removed_odr_canon_module() -> None:
    roots = [Path("orket"), Path("scripts"), Path("tests"), Path("tools")]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            module = ast.parse(text)
            for node in ast.walk(module):
                if isinstance(node, ast.ImportFrom) and node.module == "orket.kernel.v1.canon":
                    offenders.append(path.as_posix())
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "orket.kernel.v1.canon":
                            offenders.append(path.as_posix())

    assert offenders == []
