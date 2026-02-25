from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.dependency_policy import POLICY_PATH, PROJECT_ROOT, load_dependency_policy


def _expected_top_level_namespaces() -> set[str]:
    package_root = PROJECT_ROOT / "orket"
    directory_names = {path.name for path in package_root.iterdir() if path.is_dir() and path.name != "__pycache__"}
    module_names = {path.stem for path in package_root.glob("*.py")}
    return directory_names | module_names


def test_dependency_policy_maps_all_top_level_namespaces() -> None:
    policy = load_dependency_policy()
    expected = _expected_top_level_namespaces()
    missing = sorted(name for name in expected if name not in policy.top_level_to_layer)
    assert not missing, "dependency policy missing top-level namespace mappings: " + ", ".join(missing)


def test_dependency_policy_rejects_unknown_namespace() -> None:
    policy = load_dependency_policy()
    try:
        policy.layer_for_module("orket.unknown_namespace.module")
    except ValueError:
        return
    assert False, "expected ValueError for unknown namespace classification"


def test_dependency_direction_and_snapshot_use_canonical_policy(tmp_path: Path) -> None:
    check_out = tmp_path / "dependency_direction_check.json"
    snapshot_out_json = tmp_path / "dependency_snapshot.json"
    snapshot_out_md = tmp_path / "dependency_snapshot.md"

    check = subprocess.run(
        ["python", "scripts/check_dependency_direction.py", "--out", str(check_out)],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + "\n" + check.stderr
    check_payload = json.loads(check_out.read_text(encoding="utf-8"))
    assert check_payload["ok"] is True
    assert check_payload["unknown_modules"] == []
    assert check_payload["policy"]["path"] == str(POLICY_PATH.relative_to(PROJECT_ROOT))
    assert check_payload["scan"]["files_scanned"] > 0
    assert "legacy_edge_budget" in check_payload
    assert check_payload["legacy_edge_budget"]["actual_edges"] >= 0

    snapshot = subprocess.run(
        [
            "python",
            "scripts/export_dependency_graph.py",
            "--out-json",
            str(snapshot_out_json),
            "--out-md",
            str(snapshot_out_md),
        ],
        capture_output=True,
        text=True,
    )
    assert snapshot.returncode == 0, snapshot.stdout + "\n" + snapshot.stderr
    snapshot_payload = json.loads(snapshot_out_json.read_text(encoding="utf-8"))
    assert snapshot_payload["policy"]["path"] == str(POLICY_PATH.relative_to(PROJECT_ROOT))
    assert snapshot_payload["module_count"] > 0
    assert "legacy_edge_budget" in snapshot_payload
    assert all(edge["source_layer"] != "root" and edge["target_layer"] != "root" for edge in snapshot_payload["layer_edges"])


def test_dependency_direction_can_fail_on_legacy_budget_overrun(tmp_path: Path) -> None:
    check_out = tmp_path / "dependency_direction_check.json"
    result = subprocess.run(
        [
            "python",
            "scripts/check_dependency_direction.py",
            "--out",
            str(check_out),
            "--legacy-edge-max",
            "0",
            "--legacy-edge-enforcement",
            "fail",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    payload = json.loads(check_out.read_text(encoding="utf-8"))
    assert payload["legacy_edge_budget"]["exceeded"] is True


def test_architecture_docs_reference_canonical_dependency_policy() -> None:
    adr_path = PROJECT_ROOT / "docs" / "architecture" / "ADR-0001-volatility-tier-boundaries.md"
    text = adr_path.read_text(encoding="utf-8")
    assert "model/core/contracts/dependency_direction_policy.json" in text
