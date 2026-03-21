from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("sync_published_index_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


# Layer: contract
def test_sync_published_index_accepts_and_renders_governed_claim_fields(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/governance/sync_published_index.py"))
    artifact_dir = tmp_path / "General"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "artifact.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    index = {
        "catalog_v": "1.0.0",
        "updated_on": "2026-03-19",
        "root": ".",
        "highlight_id": "ART-001",
        "artifacts": [
            {
                "id": "ART-001",
                "category": "General",
                "path": "General/artifact.json",
                "title": "Governed Artifact",
                "summary": "Proof consumer row with explicit governed claim surfaces.",
                "signals": ["governed_evidence"],
                "source_path": "General/artifact.json",
                "publish_reviewed": False,
                "claim_tier": "verdict_deterministic",
                "compare_scope": "workload_s04_fixture_v1",
                "operator_surface": "workload_answer_key_scoring_verdict",
                "policy_digest": "sha256:test-policy",
                "control_bundle_hash": "sha256:test-bundle",
                "artifact_manifest_ref": "artifact_manifest.json",
                "provenance_ref": "provenance.json",
                "determinism_class": "workspace",
            }
        ],
    }
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    module._validate_index(index, index_path=index_path)
    rendered = module._render_readme(
        index,
        lane="staging",
        index_path=index_path,
        readme_path=tmp_path / "README.md",
    )

    assert "Governed Claim" in rendered
    assert "verdict_deterministic" in rendered
    assert "workload_s04_fixture_v1" in rendered
    assert "workload_answer_key_scoring_verdict" in rendered
