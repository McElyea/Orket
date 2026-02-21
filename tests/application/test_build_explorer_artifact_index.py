from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _artifact(schema: str, ref: str) -> dict:
    return {
        "schema_version": schema,
        "generated_at": "2026-02-21T00:00:00Z",
        "execution_lane": "lab",
        "vram_profile": "safe",
        "provenance": {"ref": ref},
    }


def test_build_explorer_artifact_index_writes_rows(tmp_path: Path) -> None:
    frontier = tmp_path / "frontier.json"
    context = tmp_path / "context.json"
    thermal = tmp_path / "thermal.json"
    out = tmp_path / "index.json"
    frontier.write_text(json.dumps(_artifact("explorer.frontier.v1", "r1"), indent=2) + "\n", encoding="utf-8")
    context.write_text(json.dumps(_artifact("explorer.context_ceiling.v1", "r1"), indent=2) + "\n", encoding="utf-8")
    thermal.write_text(json.dumps(_artifact("explorer.thermal_stability.v1", "r1"), indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python",
            "scripts/build_explorer_artifact_index.py",
            "--frontier",
            str(frontier),
            "--context",
            str(context),
            "--thermal",
            str(thermal),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 3
    assert payload["rows"][0]["kind"] == "frontier"
    assert payload["rows"][1]["schema_version"] == "explorer.context_ceiling.v1"
