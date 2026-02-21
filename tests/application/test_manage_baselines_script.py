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


def test_manage_baselines_health_and_prune(tmp_path: Path) -> None:
    baselines_root = tmp_path / "orket_storage" / "baselines"
    baselines_root.mkdir(parents=True, exist_ok=True)
    (baselines_root / "001.json").write_text(
        json.dumps(
            {
                "test_id": "001",
                "history": [
                    {
                        "baseline_metadata": {
                            "test_run_id": "a",
                            "hardware_fingerprint": "hw-a",
                            "task_revision": "v1",
                            "created_at": "2026-01-01T00:00:00Z",
                        },
                        "gold_telemetry": {},
                    },
                    {
                        "baseline_metadata": {
                            "test_run_id": "b",
                            "hardware_fingerprint": "hw-b",
                            "task_revision": "v2",
                            "created_at": "2026-02-01T00:00:00Z",
                        },
                        "gold_telemetry": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    health = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "health",
            "--storage-root",
            str(baselines_root),
            "--hardware-fingerprint",
            "hw-a",
            "--task-revision",
            "v1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert health.returncode == 0, health.stdout + "\n" + health.stderr
    health_payload = json.loads(health.stdout)
    assert health_payload["summary"]["tests_total"] == 1
    assert health_payload["summary"]["records_total"] == 2
    assert health_payload["summary"]["stale_records_total"] == 1
    assert health_payload["summary"]["hardware_mismatch_records_total"] == 1
    assert health_payload["summary"]["revision_mismatch_records_total"] == 1

    dry_prune = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "prune",
            "--storage-root",
            str(baselines_root),
            "--keep-last",
            "1",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_prune.returncode == 0
    dry_payload = json.loads(dry_prune.stdout)
    assert dry_payload["dry_run"] is True
    assert dry_payload["modified"][0]["removed"] == 1
    unchanged = json.loads((baselines_root / "001.json").read_text(encoding="utf-8"))
    assert len(unchanged["history"]) == 2

    prune = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "prune",
            "--storage-root",
            str(baselines_root),
            "--keep-last",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert prune.returncode == 0
    payload_after = json.loads((baselines_root / "001.json").read_text(encoding="utf-8"))
    assert len(payload_after["history"]) == 1
    assert payload_after["history"][0]["baseline_metadata"]["test_run_id"] == "b"


def test_manage_baselines_pin_and_unpin_controls_prune(tmp_path: Path) -> None:
    baselines_root = tmp_path / "orket_storage" / "baselines"
    baselines_root.mkdir(parents=True, exist_ok=True)
    (baselines_root / "001.json").write_text(
        json.dumps(
            {
                "test_id": "001",
                "history": [
                    {
                        "baseline_metadata": {
                            "test_run_id": "old-1",
                            "hardware_fingerprint": "hw-a",
                            "task_revision": "v1",
                            "created_at": "2026-01-01T00:00:00Z",
                        },
                        "gold_telemetry": {},
                    },
                    {
                        "baseline_metadata": {
                            "test_run_id": "old-2",
                            "hardware_fingerprint": "hw-a",
                            "task_revision": "v1",
                            "created_at": "2026-01-02T00:00:00Z",
                        },
                        "gold_telemetry": {},
                    },
                    {
                        "baseline_metadata": {
                            "test_run_id": "new-1",
                            "hardware_fingerprint": "hw-a",
                            "task_revision": "v1",
                            "created_at": "2026-02-01T00:00:00Z",
                        },
                        "gold_telemetry": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    pin = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "pin-baseline",
            "--storage-root",
            str(baselines_root),
            "--test-id",
            "001",
            "--baseline-ref",
            "old-1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert pin.returncode == 0, pin.stdout + "\n" + pin.stderr
    pin_payload = json.loads(pin.stdout)
    assert pin_payload["status"] == "OK"
    assert pin_payload["pinned"] is True

    prune = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "prune",
            "--storage-root",
            str(baselines_root),
            "--keep-last",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert prune.returncode == 0, prune.stdout + "\n" + prune.stderr

    payload_after_prune = json.loads((baselines_root / "001.json").read_text(encoding="utf-8"))
    remaining_ids = {
        row["baseline_metadata"]["test_run_id"] for row in payload_after_prune["history"]
    }
    assert remaining_ids == {"old-1", "new-1"}

    unpin = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "unpin-baseline",
            "--storage-root",
            str(baselines_root),
            "--test-id",
            "001",
            "--baseline-ref",
            "old-1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert unpin.returncode == 0, unpin.stdout + "\n" + unpin.stderr
    unpin_payload = json.loads(unpin.stdout)
    assert unpin_payload["status"] == "OK"
    assert unpin_payload["pinned"] is False

    prune_again = subprocess.run(
        [
            "python",
            "scripts/manage_baselines.py",
            "prune",
            "--storage-root",
            str(baselines_root),
            "--keep-last",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert prune_again.returncode == 0, prune_again.stdout + "\n" + prune_again.stderr
    final_payload = json.loads((baselines_root / "001.json").read_text(encoding="utf-8"))
    assert len(final_payload["history"]) == 1
    assert final_payload["history"][0]["baseline_metadata"]["test_run_id"] == "new-1"
