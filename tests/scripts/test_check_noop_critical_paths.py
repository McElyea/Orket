# LIFECYCLE: live
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.governance.check_noop_critical_paths import (
    check_noop_critical_paths,
    evaluate_noop_critical_paths,
    main,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def git_fixture(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_evaluate_noop_critical_paths_flags_pass_and_ellipsis_functions(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(
        source,
        "\n".join(
            [
                "def a() -> None:",
                "    pass",
                "",
                "def b() -> None:",
                "    ...",
            ]
        )
        + "\n",
    )

    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is False
    names = {row["name"] for row in payload["findings"]}
    assert "a" in names
    assert "b" in names


def test_evaluate_noop_critical_paths_ignores_abstract_methods(tmp_path: Path) -> None:
    source = tmp_path / "abstracts.py"
    _write(
        source,
        "\n".join(
            [
                "from abc import ABC, abstractmethod",
                "",
                "class C(ABC):",
                "    @abstractmethod",
                "    def run(self) -> None:",
                "        pass",
            ]
        )
        + "\n",
    )

    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["findings"] == []


def test_evaluate_noop_critical_paths_ignores_protocol_ellipsis_methods(tmp_path: Path) -> None:
    source = tmp_path / "protocol.py"
    _write(
        source,
        "\n".join(
            [
                "from typing import Protocol",
                "",
                "class Hook(Protocol):",
                "    def run(self) -> None:",
                "        ...",
            ]
        )
        + "\n",
    )

    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["findings"] == []


def test_evaluate_noop_critical_paths_parses_utf8_bom_files(tmp_path: Path) -> None:
    source = tmp_path / "bom_file.py"
    source.write_text("def run() -> int:\n    return 1\n", encoding="utf-8-sig")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["parse_errors"] == []


def test_check_noop_critical_paths_writes_out_payload_with_diff_ledger(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(source, "def run() -> int:\n    return 1\n")
    out_path = tmp_path / "out" / "noop_report.json"

    exit_code, payload = check_noop_critical_paths(roots=[tmp_path], out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


def test_main_returns_failure_when_noop_detected(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    _write(source, "def noop() -> None:\n    pass\n")
    exit_code = main(["--root", str(tmp_path)])
    assert exit_code == 1


@pytest.mark.parametrize("imports,guard", [
    ("from typing import TYPE_CHECKING", "TYPE_CHECKING"),
    ("from typing import TYPE_CHECKING as checking", "checking"),
    ("import typing as types", "types.TYPE_CHECKING"),
])
def test_type_only_declarations_preserve_runtime_else_findings(tmp_path: Path, imports: str, guard: str) -> None:
    _write(tmp_path / "typed.py", f"""
{imports}
if {guard}:
    def declared(): ...
else:
    def actual(): ...
if not {guard}:
    def actual_negated(): pass
else:
    def declared_negated(): pass
""")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert {row["name"] for row in payload["findings"]} == {"actual", "actual_negated"}


def test_imported_protocol_and_abstract_aliases_are_declarations(tmp_path: Path) -> None:
    _write(tmp_path / "declared.py", '''
import abc as abstract
import typing as types
from typing_extensions import Protocol as Port
from typing import TypeVar
from abc import abstractmethod as required
T = TypeVar('T')
class First(types.Protocol):
    def ellipsis(self):
        """Contract."""
        ...
    def placeholder(self): pass
class Second(Port):
    def documented(self):
        """Required implementation."""
class GenericPort(types.Protocol[T]):
    def generic(self): ...
class Third(abstract.ABC):
    @required
    def work(self): pass
    @abstract.abstractmethod
    async def other(self): ...
class Derived(Third):
    @required
    def inherited(self): pass
class ExplicitMeta(metaclass=abstract.ABCMeta):
    @required
    def explicit_meta(self): ...
''')
    assert evaluate_noop_critical_paths(roots=[tmp_path])["ok"] is True


@pytest.mark.parametrize("body,reason", [
    ('"""Only documentation."""', "empty_body"),
    ('"""Documentation."""\n    ...', "ellipsis"),
    ("pass\n    pass", "pass_statement"),
    ("return", "return_none"),
    ("return None", "return_none"),
    ("42", "empty_body"),
    ("value: UnknownType", "empty_body"),
])
def test_executable_empty_bodies_are_findings(tmp_path: Path, body: str, reason: str) -> None:
    _write(tmp_path / "empty.py", f"def actual():\n    {body}\n")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is False
    assert [row["reason"] for row in payload["findings"]] == [reason]


@pytest.mark.parametrize("body", ["raise NotImplementedError", "return 1", "observe()", "yield None"])
def test_actual_effect_return_and_explicit_failure_are_not_empty(tmp_path: Path, body: str) -> None:
    _write(tmp_path / "nonempty.py", f"def actual():\n    {body}\n")
    assert evaluate_noop_critical_paths(roots=[tmp_path])["ok"] is True


def test_protocol_context_does_not_hide_nested_or_concrete_implementations(tmp_path: Path) -> None:
    _write(tmp_path / "implementations.py", """
from typing import Protocol
class Port(Protocol):
    def explicit_default(self): return None
    def with_helper(self):
        def nested(): ...
        return nested
    class Nested:
        def concrete(self): ...
class Implementation(Port):
    def actual(self): ...
""")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert {row["name"] for row in payload["findings"]} == {"explicit_default", "nested", "concrete", "actual"}


@pytest.mark.parametrize("source", [
    "TYPE_CHECKING = True\nif TYPE_CHECKING:\n    def actual(): ...",
    "from typing import TYPE_CHECKING\nTYPE_CHECKING = True\nif TYPE_CHECKING:\n    def actual(): ...",
    "import typing\ntyping.TYPE_CHECKING = True\nif typing.TYPE_CHECKING:\n    def actual(): ...",
    "from foreign import Protocol\nclass Port(Protocol):\n    def actual(self): ...",
    "from typing import Protocol\nProtocol = object\nclass Port(Protocol):\n    def actual(self): ...",
    "from foreign import abstractmethod\nclass Port:\n    @abstractmethod\n    def actual(self): pass",
    "from abc import abstractmethod\n@abstractmethod\ndef actual(): pass",
    "from abc import abstractmethod\nclass Concrete:\n    @abstractmethod\n    def actual(self): pass",
    "from typing import TYPE_CHECKING\ndef enclosing(TYPE_CHECKING):\n    if TYPE_CHECKING:\n        def actual(): ...",
    "from typing import TYPE_CHECKING\ndef enclosing():\n    if TYPE_CHECKING:\n        def actual(): ...\n    TYPE_CHECKING = True",
    "from typing import TYPE_CHECKING\ndef enclosing():\n    if TYPE_CHECKING:\n        def actual(): ...\nTYPE_CHECKING = True",
    "TYPE_CHECKING = True\nclass Outer:\n    from typing import TYPE_CHECKING\n    def enclosing(self):\n        if TYPE_CHECKING:\n            def actual(): ...",
    "Protocol = object\nfor ignored in ():\n    from typing import Protocol\nclass Port(Protocol):\n    def actual(self): ...",
    "def enclosing():\n    Protocol = object\n    for ignored in ():\n        from typing import Protocol\n    class Port(Protocol):\n        def actual(self): ...",
])
def test_unresolved_rebound_and_similarly_named_bindings_do_not_exempt(tmp_path: Path, source: str) -> None:
    _write(tmp_path / "rebound.py", source + "\n")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert [row["name"] for row in payload["findings"]] == ["actual"]


@pytest.mark.parametrize("source", [b"def broken(:", b"\xff"])
def test_unreadable_syntax_and_encoding_fail_closed(tmp_path: Path, source: bytes) -> None:
    (tmp_path / "broken.py").write_bytes(source)
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is False
    assert len(payload["parse_errors"]) == 1


def test_missing_and_empty_roots_fail_closed(tmp_path: Path) -> None:
    assert evaluate_noop_critical_paths(roots=[tmp_path / "absent"])["ok"] is False
    assert evaluate_noop_critical_paths(roots=[])["ok"] is False


def test_inventory_ignores_local_files_and_rejects_discovery_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(tmp_path / ".gitignore", "ignored/\n")
    _write(tmp_path / "ignored" / "empty.py", "def actual(): ...\n")
    _write(tmp_path / "visible.py", "def actual(): return 1\n")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is True
    assert payload["scanned_files"] == 1
    # Workspace-local fixtures must not discover the enclosing worktree.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    (tmp_path / ".git").rename(tmp_path / "git-disabled")
    payload = evaluate_noop_critical_paths(roots=[tmp_path])
    assert payload["ok"] is False
    assert "scan_inventory_error" in payload["parse_errors"][0]["error"]
