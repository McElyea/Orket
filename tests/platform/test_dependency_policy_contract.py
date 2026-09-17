"""Contract proof for the canonical allowed-edge policy and native commands."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.common.git_inventory import git_list_files
from scripts.governance.dependency_imports import module_from_path
from scripts.governance.dependency_policy import LAYERS, PROJECT_ROOT, load_dependency_policy
from tests.helpers.dependency_repository import make_repository, run_command

pytestmark = pytest.mark.contract


def test_dependency_policy_maps_all_git_visible_modules() -> None:
    """Layer: contract. Every source module maps to one of the five normative layers."""
    policy = load_dependency_policy()
    paths = [p for p in git_list_files(PROJECT_ROOT) if p.suffix == ".py" and p.is_relative_to(PROJECT_ROOT / "orket")]
    assert paths
    assert all(policy.layer_for_module(module_from_path(p, PROJECT_ROOT)) in LAYERS for p in paths)
    with pytest.raises(ValueError, match="Unclassified"):
        policy.layer_for_module("orket.unknown_namespace.module")


@pytest.mark.parametrize(
    "source,target,expected",
    [
        ("application", "core", 0),
        ("core", "application", 1),
        ("adapters", "application", 1),
        ("interfaces", "adapters", 1),
        ("core", "services", 1),
        ("core", "platform", 1),
        ("runtime", "interfaces", 1),
        ("unknown_namespace", "core", 1),
    ],
)
def test_native_checker_enforces_normative_edges(tmp_path: Path, source: str, target: str, expected: int) -> None:
    """Layer: contract. Actual native commands accept the allowed edge and refuse counterexamples."""
    make_repository(
        tmp_path, {f"orket/{source}/source.py": f"import orket.{target}.target\n", f"orket/{target}/target.py": ""}
    )
    process, report = run_command(tmp_path)
    assert process.returncode == expected, process.stderr
    assert report["collection_ok"] and report["verdict"]["ok"] == (expected == 0)


def test_checker_and_export_share_observation_and_keep_verdict_separate(tmp_path: Path) -> None:
    """Layer: contract. Export success cannot stand in for a passing dependency verdict."""
    make_repository(
        tmp_path, {"orket/core/source.py": "import orket.application.target", "orket/application/target.py": ""}
    )
    check, verdict = run_command(tmp_path)
    exported, snapshot = run_command(tmp_path, exporter=True)
    assert check.returncode == 1 and exported.returncode == 0
    assert not verdict["verdict"]["ok"] and not snapshot["verdict"]["ok"]
    assert verdict["observed"] == snapshot["observed"]
    assert verdict["policy"] == snapshot["policy"]
    assert "Policy verdict: `False`" in (tmp_path / "export.md").read_text(encoding="utf-8")
    _, repeated = run_command(tmp_path, exporter=True)
    assert len(repeated["diff_ledger"]) >= 2


def _exception() -> dict:
    return {
        "id": "fixture-exception",
        "source": "orket.adapters.source",
        "target": "orket.application.target",
        "owner": "Fixture owner",
        "reason": "Exact legacy fixture edge",
        "introduced": "2026-01-01",
        "removal": "Delete the fixture after this test",
        "expires": "2099-01-01",
    }


def test_exception_consumption_does_not_hide_another_edge(tmp_path: Path) -> None:
    """Layer: contract. One exact exception cannot cover a sibling dependency."""
    path = make_repository(
        tmp_path, {"orket/adapters/source.py": "import orket.application.target", "orket/application/target.py": ""}
    )
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["exceptions"] = [_exception()]
    path.write_text(json.dumps(policy), encoding="utf-8")
    process, report = run_command(tmp_path)
    assert process.returncode == 0
    assert report["verdict"]["exceptions"]["consumed"] == [_exception()]
    (tmp_path / "orket/adapters/second.py").write_text("import orket.application.target", encoding="utf-8")
    process, report = run_command(tmp_path)
    assert process.returncode == 1
    assert report["verdict"]["violations"][0]["source"] == "orket.adapters.second"


@pytest.mark.parametrize(
    "field,value",
    [("owner", ""), ("source", "orket.adapters.*"), ("introduced", "2099-01-01"), ("expires", "2026-01-01")],
)
def test_invalid_or_expired_exceptions_are_refused(tmp_path: Path, field: str, value: str) -> None:
    """Layer: contract. Exceptions require complete bounded metadata and an unexpired lifetime."""
    path = make_repository(tmp_path, {"orket/core/target.py": ""})
    policy = json.loads(path.read_text(encoding="utf-8"))
    row = _exception()
    row[field] = value
    policy["exceptions"] = [row]
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(ValueError):
        load_dependency_policy(path, today=date(2026, 9, 14))


def test_exact_exception_does_not_waive_authority_cycle(tmp_path: Path) -> None:
    """Layer: contract. A permitted exceptional edge still participates in cycle detection."""
    path = make_repository(
        tmp_path,
        {
            "orket/adapters/source.py": "import orket.application.target",
            "orket/application/target.py": "import orket.adapters.source",
        },
    )
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["exceptions"] = [_exception()]
    path.write_text(json.dumps(policy), encoding="utf-8")
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report["verdict"]["violations"]
    assert report["verdict"]["authority_cycles"] == [
        {"modules": ["orket.adapters.source", "orket.application.target"], "layers": ["adapters", "application"]}
    ]


def test_undeclared_decision_contract_and_adapter_are_refused(tmp_path: Path) -> None:
    """Layer: contract. Decision nodes cannot reach arbitrary core implementations or undeclared adapters."""
    make_repository(
        tmp_path,
        {
            "orket/decision_nodes/source.py": "import orket.core.internal\nimport orket.adapters.target",
            "orket/core/internal.py": "",
            "orket/adapters/target.py": "",
        },
    )
    process, report = run_command(tmp_path)
    assert process.returncode == 1
    assert {r["target"] for r in report["verdict"]["violations"]} == {"orket.core.internal", "orket.adapters.target"}


def test_duplicate_policy_keys_fail_instead_of_selecting_the_last_authority(tmp_path: Path) -> None:
    """Layer: contract. Duplicate JSON authority fields are invalid input."""
    path = make_repository(tmp_path, {"orket/core/target.py": ""})
    raw = path.read_text(encoding="utf-8")
    path.write_text(
        raw.replace('"schema_version": "2.0.0"', '"schema_version": "1.0.0", "schema_version": "2.0.0"'),
        encoding="utf-8",
    )
    process, report = run_command(tmp_path)
    assert process.returncode == 1 and not report["collection_ok"]
    assert "Duplicate dependency policy key" in report["verdict"]["analysis_errors"][0]["detail"]
