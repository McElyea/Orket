from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_retention_plan_and_policy_check_scripts(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.json"
    out_plan = tmp_path / "retention_plan.json"
    out_check = tmp_path / "retention_check.json"

    payload = {
        "entries": [
            {
                "path": "smoke/api-runtime/2026-02-01/run-old.json",
                "updated_at": "2026-02-01T00:00:00+00:00",
                "size_bytes": 5,
            },
            {
                "path": "smoke/api-runtime/2026-02-24/run-new.json",
                "updated_at": "2026-02-24T00:00:00+00:00",
                "size_bytes": 5,
            },
            {
                "path": "checks/2026-02-24/check_alpha.json",
                "updated_at": "2026-02-24T00:00:00+00:00",
                "size_bytes": 1,
                "status": "pass",
            },
            {
                "path": "artifacts/2025-01-01/heavy.bin",
                "updated_at": "2025-01-01T00:00:00+00:00",
                "size_bytes": 12,
                "pinned": True,
            },
        ]
    }
    inventory.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    plan = subprocess.run(
        [
            "python",
            "scripts/retention_plan.py",
            "--inventory",
            str(inventory),
            "--as-of",
            "2026-02-24T00:00:00+00:00",
            "--smoke-keep-latest",
            "1",
            "--artifacts-size-cap-gb",
            "1",
            "--out",
            str(out_plan),
        ],
        capture_output=True,
        text=True,
    )
    assert plan.returncode == 0, plan.stdout + "\n" + plan.stderr
    assert out_plan.exists()
    plan_payload = json.loads(out_plan.read_text(encoding="utf-8"))
    assert plan_payload["ok"] is True
    assert plan_payload["source"]["mode"] == "dry-run"

    check = subprocess.run(
        [
            "python",
            "scripts/check_retention_policy.py",
            "--plan",
            str(out_plan),
            "--out",
            str(out_check),
            "--require-safety",
        ],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + "\n" + check.stderr
    assert out_check.exists()
    check_payload = json.loads(out_check.read_text(encoding="utf-8"))
    assert check_payload["ok"] is True

