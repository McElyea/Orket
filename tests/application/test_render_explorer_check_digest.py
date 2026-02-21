from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_render_explorer_check_digest_writes_markdown(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    out = tmp_path / "digest.md"
    summary.write_text(
        json.dumps(
            {
                "status": "PASS",
                "statuses": {"ingestion": "PASS", "rollup": "PASS", "guards": "SKIP"},
                "artifacts": {"ingestion": "a.json", "rollup": "b.json", "guards": "c.json"},
                "failed_checks": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/render_explorer_check_digest.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    text = out.read_text(encoding="utf-8")
    assert "# Explorer Check Digest" in text
    assert "| ingestion | PASS | `a.json` |" in text
