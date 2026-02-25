from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_workitem_migration_dry_run_script_emits_report(tmp_path: Path) -> None:
    in_path = tmp_path / "legacy.json"
    out_path = tmp_path / "report.json"
    in_path.write_text(
        json.dumps(
            [
                {"id": "ROCK-1", "type": "rock", "status": "ready"},
                {"id": "EPIC-1", "type": "epic", "rock_id": "ROCK-1", "status": "in_progress"},
                {"id": "ISSUE-1", "type": "issue", "epic_id": "EPIC-1", "status": "done"},
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/workitem_migration_dry_run.py",
            "--in",
            str(in_path),
            "--out",
            str(out_path),
        ],
        check=True,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["mode"] == "dry_run"
    assert payload["total_records"] == 3
    assert payload["mapped_kind_counts"] == {"initiative": 1, "project": 1, "task": 1}
