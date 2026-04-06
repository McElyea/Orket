# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.build_cross_lane_dependency_map import (
    build_cross_lane_dependency_map,
    build_cross_lane_dependency_mermaid,
    export_cross_lane_dependency_map,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# Layer: contract
def test_build_cross_lane_dependency_map_extracts_plan_dependencies(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "ROADMAP.md",
        "\n".join(
            [
                "# Orket Roadmap",
                "## Priority Now",
                "1. lane alpha -- Canonical implementation plan: `docs/projects/future/ALPHA.md`.",
            ]
        )
        + "\n",
    )
    _write(
        tmp_path / "docs" / "projects" / "future" / "ALPHA.md",
        "\n".join(
            [
                "# Alpha Plan",
                "Related authority inputs:",
                "1. `docs/specs/ONE.md`",
                "2. `docs/specs/TWO.md`",
            ]
        )
        + "\n",
    )

    payload = build_cross_lane_dependency_map(workspace=tmp_path)
    assert payload["ok"] is True
    assert payload["lane_count"] == 1
    assert payload["edge_count"] == 2
    dependencies = payload["lanes"][0]["dependencies"]
    assert dependencies == ["docs/specs/ONE.md", "docs/specs/TWO.md"]


# Layer: contract
def test_build_cross_lane_dependency_mermaid_contains_lane_and_edges(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "ROADMAP.md",
        "\n".join(
            [
                "# Orket Roadmap",
                "## Priority Now",
                "1. lane beta -- Canonical implementation plan: `docs/projects/future/BETA.md`.",
            ]
        )
        + "\n",
    )
    _write(
        tmp_path / "docs" / "projects" / "future" / "BETA.md",
        "See `docs/specs/THREE.md`.\n",
    )
    payload = build_cross_lane_dependency_map(workspace=tmp_path)
    mermaid = build_cross_lane_dependency_mermaid(payload)
    assert mermaid.startswith("graph LR\n")
    assert 'lane_0["lane beta"]' in mermaid
    assert 'dep_0_0["docs/specs/THREE.md"]' in mermaid


# Layer: integration
def test_export_cross_lane_dependency_map_writes_json_and_mermaid(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "ROADMAP.md",
        "\n".join(
            [
                "# Orket Roadmap",
                "## Priority Now",
                "1. lane gamma -- Canonical implementation plan: `docs/projects/future/GAMMA.md`.",
            ]
        )
        + "\n",
    )
    _write(tmp_path / "docs" / "projects" / "future" / "GAMMA.md", "No dependencies.\n")
    out_json = tmp_path / "docs" / "generated" / "map.json"
    out_mermaid = tmp_path / "docs" / "generated" / "map.mmd"

    payload = export_cross_lane_dependency_map(
        workspace=tmp_path,
        out_json=out_json,
        out_mermaid=out_mermaid,
    )
    assert payload["ok"] is True
    assert out_mermaid.exists()
    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written
