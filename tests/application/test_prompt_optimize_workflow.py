from __future__ import annotations

import json
from pathlib import Path

from scripts.prompt_lab.optimize_prompts import generate_candidates


def _seed_assets(root: Path) -> None:
    roles = root / "model" / "core" / "roles"
    dialects = root / "model" / "core" / "dialects"
    roles.mkdir(parents=True, exist_ok=True)
    dialects.mkdir(parents=True, exist_ok=True)

    role_payload = {
        "id": "ARCHITECT",
        "summary": "architect",
        "type": "utility",
        "description": "Architect role.",
        "tools": ["write_file", "update_issue_status"],
        "prompt_metadata": {
            "id": "role.architect",
            "version": "1.0.0",
            "status": "stable",
            "owner": "core",
            "updated_at": "2026-02-14",
            "lineage": {"parent": None},
            "changelog": [{"version": "1.0.0", "date": "2026-02-14", "notes": "initial"}],
        },
    }
    dialect_payload = {
        "model_family": "generic",
        "dsl_format": "{\"tool\":\"write_file\",\"args\":{\"path\":\"a\",\"content\":\"b\"}}",
        "constraints": ["Return JSON only."],
        "hallucination_guard": "No extra prose",
        "prompt_metadata": {
            "id": "dialect.generic",
            "version": "2.1.3",
            "status": "stable",
            "owner": "core",
            "updated_at": "2026-02-14",
            "lineage": {"parent": None},
            "changelog": [{"version": "2.1.3", "date": "2026-02-14", "notes": "initial"}],
        },
    }
    (roles / "architect.json").write_text(json.dumps(role_payload, indent=2), encoding="utf-8")
    (dialects / "generic.json").write_text(json.dumps(dialect_payload, indent=2), encoding="utf-8")


def test_generate_candidates_writes_to_output_only(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    source_role = tmp_path / "model" / "core" / "roles" / "architect.json"
    source_before = source_role.read_text(encoding="utf-8")

    out_dir = tmp_path / "prompts" / "candidates"
    manifest = generate_candidates(
        root=tmp_path,
        out_dir=out_dir,
        kind="all",
        source_status="stable",
        bump="patch",
        note="opt-run",
    )

    assert manifest["count"] == 2
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "role" / "architect.1.0.1.candidate.json").exists()
    assert (out_dir / "dialect" / "generic.2.1.4.candidate.json").exists()
    # Critical safety check: source asset remains unchanged.
    assert source_role.read_text(encoding="utf-8") == source_before


def test_generate_candidates_filters_by_kind_and_status(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    role_path = tmp_path / "model" / "core" / "roles" / "architect.json"
    role_payload = json.loads(role_path.read_text(encoding="utf-8"))
    role_payload["prompt_metadata"]["status"] = "deprecated"
    role_path.write_text(json.dumps(role_payload, indent=2), encoding="utf-8")

    out_dir = tmp_path / "prompts" / "candidates"
    manifest = generate_candidates(
        root=tmp_path,
        out_dir=out_dir,
        kind="role",
        source_status="stable",
        bump="minor",
    )
    assert manifest["count"] == 0
    assert not (out_dir / "role" / "architect.1.1.0.candidate.json").exists()
