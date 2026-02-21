from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_manage_baselines_resolve_statuses(tmp_path: Path) -> None:
    baselines_root = tmp_path / "orket_storage" / "baselines"
    baselines_root.mkdir(parents=True, exist_ok=True)
    (baselines_root / "001.json").write_text(
        json.dumps(
            {
                "test_id": "001",
                "history": [
                    {
                        "baseline_metadata": {
                            "test_run_id": "ref-old",
                            "hardware_fingerprint": "linux-6|cpu|8c|32gb|none",
                            "task_revision": "v1",
                            "created_at": "2026-01-01T00:00:00Z",
                        },
                        "gold_telemetry": {"adherence_score": 1.0, "peak_memory_rss": 3000.0, "total_latency": 10.0},
                    },
                    {
                        "baseline_metadata": {
                            "test_run_id": "ref-new",
                            "hardware_fingerprint": "linux-6|cpu|8c|32gb|none",
                            "task_revision": "v1",
                            "created_at": "2026-02-01T00:00:00Z",
                        },
                        "gold_telemetry": {"adherence_score": 1.0, "peak_memory_rss": 2800.0, "total_latency": 9.0},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    ok = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "resolve",
            "--storage-root",
            str(baselines_root),
            "--test-id",
            "001",
            "--hardware-fingerprint",
            "linux-6|cpu|8c|32gb|none",
            "--task-revision",
            "v1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + "\n" + ok.stderr
    ok_payload = json.loads(ok.stdout)
    assert ok_payload["status"] == "OK"
    assert ok_payload["record"]["baseline_metadata"]["test_run_id"] == "ref-new"

    rev_mismatch = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "resolve",
            "--storage-root",
            str(baselines_root),
            "--test-id",
            "001",
            "--hardware-fingerprint",
            "linux-6|cpu|8c|32gb|none",
            "--task-revision",
            "v2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rev_mismatch.returncode == 0
    rev_payload = json.loads(rev_mismatch.stdout)
    assert rev_payload["status"] == "REV_MISMATCH"


def test_manage_baselines_pin_updates_task_file(tmp_path: Path) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text(
        json.dumps({"id": "001", "acceptance_contract": {"mode": "function"}}, indent=2),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "pin",
            "--task-file",
            str(task_file),
            "--baseline-ref",
            "ref-1234",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(task_file.read_text(encoding="utf-8"))
    assert payload["acceptance_contract"]["baseline_ref"] == "ref-1234"
