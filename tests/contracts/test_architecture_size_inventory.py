"""Contract: inventory admission and contextual size facts, not runtime defects."""
from __future__ import annotations

import hashlib
import subprocess

import pytest

from scripts.governance.architecture_size_inventory import collect_architecture_sizes

pytestmark = pytest.mark.contract


def repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "orket").mkdir()
    return tmp_path


def test_nested_router_spans_retain_context_without_exempting_factories(tmp_path):
    root = repository(tmp_path)
    source = "def build_router():\n    if True:\n        @router.get('/value')\n        async def value():\n"
    source += "            item = 1\n" * 71 + "            return item\n    return router\n"
    (root / "orket/routes.py").write_text(source, encoding="utf-8")
    result = collect_architecture_sizes(root)
    assert result["collection_ok"] is True
    assert result["span_semantics"] == "inclusive_nested_definitions"
    assert result["functions_over_70_total"] == 2
    factory, route = result["functions_over_70"]
    assert (factory["qualified_name"], factory["direct_nested_definitions"]) == ("build_router", 1)
    assert route["qualified_name"] == "build_router.value"
    assert route["enclosing_scopes"] == [{"kind": "function", "name": "build_router"}]
    assert route["route_decorator_syntax"] == ["router.get"]
    assert route["is_async"] is True
    assert route["lines"] == 73 and factory["lines"] == 77


def test_size_inventory_excludes_ignored_sources_and_includes_untracked(tmp_path):
    root = repository(tmp_path)
    (root / ".gitignore").write_text("orket/ignored.py\n", encoding="utf-8")
    (root / "orket/ignored.py").write_text("not valid python !", encoding="utf-8")
    (root / "orket/empty.py").write_bytes(b"")
    (root / "orket/value.py").write_bytes(b"\xef\xbb\xbfvalue = 1\n")
    result = collect_architecture_sizes(root)
    assert result["collection_ok"] is True and result["python_files_scanned"] == 2
    assert set(result["source_sha256"]) == {"orket/empty.py", "orket/value.py"}
    assert result["source_sha256"]["orket/value.py"] == hashlib.sha256(b"\xef\xbb\xbfvalue = 1\n").hexdigest()
    assert result["parse_errors"] == []


def test_complete_oversized_inventory_keeps_rows_beyond_largest_summary(tmp_path):
    root = repository(tmp_path)
    for index in range(27):
        (root / f"orket/item_{index:02}.py").write_text("x = 1\n" * 401, encoding="utf-8")
    result = collect_architecture_sizes(root)
    assert result["collection_ok"] is True
    assert len(result["files_over_400"]) == result["files_over_400_total"] == 27
    assert result["largest_files"] == result["files_over_400"][:25]
    assert result["files_over_400"][-1] == {"path": "orket/item_26.py", "lines": 401}


def test_class_and_nested_method_names_preserve_lexical_context(tmp_path):
    root = repository(tmp_path)
    source = "# coding: latin-1\n# caf\xe9\nclass Service:\n    def execute(self):\n"
    source += "        class Nested:\n            def execute(self):\n" + "                item = 1\n" * 71
    (root / "orket/service.py").write_bytes(source.encode("latin-1"))
    result = collect_architecture_sizes(root)
    assert result["collection_ok"] is True
    outer, inner = result["functions_over_70"]
    assert outer["qualified_name"] == "Service.execute" and outer["direct_nested_definitions"] == 1
    assert inner["qualified_name"] == "Service.execute.Nested.execute"
    assert inner["enclosing_scopes"] == [{"kind": "class", "name": "Service"},
                                          {"kind": "function", "name": "execute"},
                                          {"kind": "class", "name": "Nested"}]


@pytest.mark.parametrize("failure", ["empty", "missing_root", "not_git", "syntax"])
def test_incomplete_size_observation_cannot_pass(tmp_path, monkeypatch, failure):
    root = repository(tmp_path) if failure != "not_git" else tmp_path
    if failure == "missing_root":
        (root / "orket").rmdir()
    elif failure == "not_git":
        (root / "orket").mkdir()
        (root / "orket/value.py").write_text("value = 1\n", encoding="utf-8")
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(root.parent))
    elif failure == "syntax":
        (root / "orket/invalid.py").write_text("def missing(:", encoding="utf-8")
        (root / "orket/healthy.py").write_text("value = 1\n", encoding="utf-8")
    result = collect_architecture_sizes(root)
    assert result["collection_ok"] is False
    assert result["parse_errors"] or result["inventory_errors"]
    if failure == "syntax":
        assert result["parsed_files_total"] == 1 and result["python_files_scanned"] == 2
        assert result["parse_errors"][0]["path"] == "orket/invalid.py"


def test_native_source_change_during_parse_refuses_collection(tmp_path, monkeypatch):
    from scripts.governance import architecture_size_inventory as inventory

    root = repository(tmp_path)
    path = root / "orket/value.py"
    path.write_text("value = 1\n", encoding="utf-8")
    parse = inventory.ast.parse

    def mutate_after_parse(*args, **kwargs):
        tree = parse(*args, **kwargs)
        path.write_text("value = 2\n", encoding="utf-8")
        return tree

    monkeypatch.setattr(inventory.ast, "parse", mutate_after_parse)
    result = collect_architecture_sizes(root)
    assert result["collection_ok"] is False
    assert result["inventory_errors"] == ["source_changed_during_scan: orket/value.py"]
