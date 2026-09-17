"""Contract coverage of real Git discovery and static import refusal boundaries."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.governance.dependency_analysis import analyze_repository
from scripts.governance.dependency_policy import load_dependency_policy
from tests.helpers.dependency_repository import make_repository, run_command

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "statement",
    [
        "import orket.application.target",
        "from ..application import target",
        "from orket import application",
        "from importlib import import_module as load\nload('orket.application.target')",
        "import importlib as library\nload = library.import_module\nload(name='orket.application.target')",
        "import importlib\ngetattr(importlib, 'import_module')('orket.' + 'application.target')",
        "import builtins\nbuiltins.__dict__['__import__']('orket.application.target')",
        "__builtins__.get('__import__')('orket.application.target')",
        "__import__('orket', fromlist=['application'])",
        "import sys\nvalue = sys.modules['orket.application.target']",
        "from importlib import import_module\nimport_module('.target', 'orket.application')",
    ],
)
def test_import_spellings_cannot_hide_forbidden_edges(tmp_path: Path, statement: str) -> None:
    """Layer: contract. Parse real source without importing or executing it."""
    policy = make_repository(
        tmp_path,
        {"orket/core/source.py": statement, "orket/application/target.py": "raise RuntimeError('must not execute')"},
    )
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert not report["verdict"]["ok"]
    assert any(r["target"].startswith("orket.application") for r in report["verdict"]["violations"])


@pytest.mark.parametrize(
    "statement,code",
    [
        ("import importlib\nimportlib.import_module(user_input)", "unresolved_dynamic_import"),
        ("import importlib\ngetattr(importlib, selected)('orket.core.target')", "unresolved_import_attribute"),
        ("from importlib import import_module\ncallback(import_module)", "importer_escape"),
        ("import importlib\nobj.loader = importlib.import_module", "importer_escape"),
        ("exec(user_input)", "dynamic_code_loading"),
        ("loader.exec_module(module)", "dynamic_code_loading"),
        ("from . import *", "unresolved_star_import"),
        ("from ....outside import value", "relative_import_beyond_package"),
        ("value = globals()[name]", "unresolved_reflection"),
        ("import sys\nvalue = sys.modules[name]", "unresolved_module_registry"),
        ("import importlib\nimportlib.__dict__[name]('orket.core.target')", "unresolved_import_attribute"),
        ("__builtins__[name]('orket.core.target')", "unresolved_import_attribute"),
        ("import importlib\ncallback(importlib)", "import_namespace_escape"),
        ("import importlib.util\ngetattr(importlib.util, selected)(name)", "unresolved_import_attribute"),
        ("import pkgutil\ngetattr(pkgutil, selected)(name)", "unresolved_import_attribute"),
        ("import runpy\ngetattr(runpy, selected)(name)", "unresolved_import_attribute"),
    ],
)
def test_unresolved_routes_are_explicit_failures(tmp_path: Path, statement: str, code: str) -> None:
    """Layer: contract. Unknown targets cannot become an empty successful import set."""
    policy = make_repository(tmp_path, {"orket/core/source.py": statement})
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert not report["verdict"]["ok"]
    assert code in {r["code"] for r in report["verdict"]["analysis_errors"]}


@pytest.mark.parametrize(
    "statement",
    [
        "__import__('importlib').import_module('orket.application.target')",
        "import importlib\nlibrary = importlib.import_module(name='importlib')\nlibrary.import_module('orket.application.target')",
        "__import__('builtins').__import__('orket.application.target')",
        "__import__('runpy').run_module('orket.application.target')",
        "__import__('pkgutil').resolve_name('orket.application.target')",
        "import importlib, sys\nlibrary = sys.modules['importlib']\nlibrary.import_module('orket.application.target')",
    ],
)
def test_imported_importer_namespaces_cannot_hide_edges(tmp_path: Path, statement: str) -> None:
    """Layer: contract. Native commands follow concrete loader namespaces through nested imports."""
    make_repository(tmp_path, {"orket/core/source.py": statement, "orket/application/target.py": ""})
    process, report = run_command(tmp_path)
    assert process.returncode == 1
    assert any(r["target"] == "orket.application.target" for r in report["verdict"]["violations"])


def test_imported_importer_namespace_preserves_allowed_edge(tmp_path: Path) -> None:
    """Layer: contract. Loading an importer namespace cannot be rejected unconditionally."""
    make_repository(
        tmp_path,
        {
            "orket/application/source.py": "__import__('importlib').import_module('orket.core.target')",
            "orket/core/target.py": "",
        },
    )
    process, report = run_command(tmp_path)
    assert process.returncode == 0 and report["verdict"]["ok"]
    assert any(r["target"] == "orket.core.target" for r in report["observed"]["edges"])


@pytest.mark.parametrize(
    "source",
    [
        b"\xef\xbb\xbfimport orket.application.target\n",
        b"# coding: latin-1\n# caf\xe9\nimport orket.application.target\n",
    ],
)
def test_python_source_encodings_preserve_dependency_edges(tmp_path: Path, source: bytes) -> None:
    """Layer: contract. Valid BOM/encoding declarations cannot hide imports."""
    policy = make_repository(tmp_path, {"orket/core/source.py": source, "orket/application/target.py": ""})
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert not report["verdict"]["analysis_errors"]
    assert report["verdict"]["violations"]


def test_literal_alias_module_identity_is_observed(tmp_path: Path) -> None:
    """Layer: contract. Existing literal alias imports retain their concrete dependency."""
    code = "import importlib, sys\nmodule = importlib.import_module('orket.core.target')\nsys.modules[__name__] = sys.modules[module.__name__]"
    policy = make_repository(tmp_path, {"orket/application/source.py": code, "orket/core/target.py": ""})
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert report["verdict"]["ok"]
    assert any(r["target"] == "orket.core.target" for r in report["observed"]["edges"])


def test_importer_alias_assignment_preserves_an_allowed_call(tmp_path: Path) -> None:
    """Layer: contract. Binding a local alias is not an escaped importer."""
    policy = make_repository(
        tmp_path,
        {
            "orket/application/source.py": "import importlib as namespace\nload = namespace.import_module\nload('orket.core.target')",
            "orket/core/target.py": "",
        },
    )
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert report["verdict"]["ok"]


def test_git_visibility_and_parse_failure_are_truthful(tmp_path: Path) -> None:
    """Layer: contract. Ignored sources stay out; forcing one into Git exposes its parse error."""
    make_repository(
        tmp_path,
        {"orket/core/good.py": "", "orket/core/ignored.py": "broken python !", ".gitignore": "orket/core/ignored.py\n"},
    )
    positive, report = run_command(tmp_path)
    assert positive.returncode == 0 and report["verdict"]["ok"]
    added = subprocess.run(
        ["git", "-C", str(tmp_path), "add", "-f", "orket/core/ignored.py"], capture_output=True, timeout=20
    )
    assert added.returncode == 0
    negative, report = run_command(tmp_path)
    assert negative.returncode == 1 and not report["collection_ok"] and not report["verdict"]["ok"]
    assert report["verdict"]["analysis_errors"][0]["code"] == "source_parse_or_read_error"


def test_nonrepository_discovery_is_not_an_empty_green(tmp_path: Path) -> None:
    """Layer: contract. The native command reports Git failure with context."""
    from scripts.governance.dependency_policy import POLICY_PATH

    (tmp_path / "policy.json").write_bytes(POLICY_PATH.read_bytes())
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report["collection_ok"]
    assert report["verdict"]["analysis_errors"][0]["code"] == "dependency_collection_error"


def test_alias_rebinding_analysis_terminates(tmp_path: Path) -> None:
    """Layer: contract. A self-referential assignment cannot grow the alias lattice forever."""
    make_repository(tmp_path, {"orket/core/source.py": "import importlib as loader\nloader = loader.member"})
    process, report = run_command(tmp_path)
    assert process.returncode == 0 and report["verdict"]["ok"]


def test_missing_from_member_is_not_treated_as_a_valid_package_import(tmp_path: Path) -> None:
    """Layer: contract. A missing module/member cannot disappear behind a known package."""
    make_repository(tmp_path, {"orket/core/source.py": "from orket import missing_namespace"})
    process, report = run_command(tmp_path)
    assert process.returncode == 1
    assert any(
        r["code"] == "unresolved_local_member:orket.missing_namespace" for r in report["verdict"]["analysis_errors"]
    )


def test_package_precedence_keeps_shadowed_source_visible(tmp_path: Path) -> None:
    """Layer: contract. A package import resolves correctly without discarding its same-named file."""
    policy = make_repository(
        tmp_path,
        {
            "orket/core/source.py": "import orket.application.target",
            "orket/application/target.py": "",
            "orket/application/target/__init__.py": "",
        },
    )
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert "orket.application.target" in report["observed"]["modules"]
    assert "orket.application.target.__init__" in report["observed"]["modules"]
    assert report["verdict"]["violations"][0]["target"] == "orket.application.target.__init__"


def test_literal_forwarder_preserves_exports_and_parent_identity(tmp_path: Path) -> None:
    """Layer: contract. A literal compatibility forwarder is resolved without an exception or execution."""
    code = (
        "import sys as s\nfrom importlib import import_module as load\n"
        "module = load('orket.application.target')\ns.modules[__name__] = module\n"
        "parent = s.modules[__name__.rsplit('.', 1)[0]]\n"
    )
    policy = make_repository(
        tmp_path,
        {
            "orket/application/alias.py": code,
            "orket/application/target.py": "class Value: pass",
            "orket/application/caller.py": "from orket.application.alias import Value",
        },
    )
    report = analyze_repository(tmp_path, load_dependency_policy(policy))
    assert report["verdict"]["ok"]
    assert any(
        r["source"] == "orket.application.alias" and r["target"] == "orket.application.target"
        for r in report["observed"]["edges"]
    )
