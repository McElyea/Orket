from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_build_context_sweep_rollup_emits_compact_summary(tmp_path: Path) -> None:
    ceiling = tmp_path / "context_ceiling.json"
    out = tmp_path / "rollup.json"
    ceiling.write_text(
        json.dumps(
            {
                "execution_lane": "lab",
                "vram_profile": "safe",
                "provenance": {"ref": "r1"},
                "safe_context_ceiling": 8192,
                "points": [
                    {"context": 4096, "passed": True},
                    {"context": 8192, "passed": True},
                    {"context": 16384, "passed": False},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/build_context_sweep_rollup.py",
            "--context-ceiling",
            str(ceiling),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "explorer.context_sweep_rollup.v1"
    assert payload["contexts_total"] == 3
    assert payload["contexts_passed"] == 2
    assert payload["contexts_failed"] == 1
    assert payload["failed_contexts"] == [16384]
