from __future__ import annotations

import json
from pathlib import Path

from scripts.common.rerun_diff_ledger import append_payload_history, write_json_with_diff_ledger, write_payload_with_diff_ledger


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_payload_with_diff_ledger_tracks_initial_noop_and_change(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    first = {"schema_version": "v1", "ok": True, "counts": {"passed": 2, "failed": 0}}

    persisted_first = write_payload_with_diff_ledger(out, first, max_entries=10)
    assert persisted_first["diff_ledger"][0]["diff"]["initial_write"] is True
    assert persisted_first["diff_ledger"][0]["changed"] is True

    persisted_second = write_payload_with_diff_ledger(out, first, max_entries=10)
    assert len(persisted_second["diff_ledger"]) == 2
    assert persisted_second["diff_ledger"][-1]["changed"] is False
    assert persisted_second["diff_ledger"][-1]["diff"]["changed_paths"] == 0
    assert persisted_second["diff_ledger"][-1]["diff"]["added_paths"] == 0
    assert persisted_second["diff_ledger"][-1]["diff"]["removed_paths"] == 0

    third = {"schema_version": "v1", "ok": False, "counts": {"passed": 1, "failed": 1}, "note": "rerun"}
    persisted_third = write_payload_with_diff_ledger(out, third, max_entries=10)
    assert len(persisted_third["diff_ledger"]) == 3
    assert persisted_third["diff_ledger"][-1]["changed"] is True
    assert persisted_third["diff_ledger"][-1]["diff"]["initial_write"] is False
    assert persisted_third["diff_ledger"][-1]["diff"]["sample_paths"]


def test_write_payload_with_diff_ledger_respects_max_entries(tmp_path: Path) -> None:
    out = tmp_path / "trimmed.json"
    for idx in range(6):
        payload = {"schema_version": "v1", "run": idx}
        write_payload_with_diff_ledger(out, payload, max_entries=3)
    persisted = _load(out)
    assert len(persisted["diff_ledger"]) == 3


def test_append_payload_history_appends_dict_entries(tmp_path: Path) -> None:
    out = tmp_path / "history.json"
    append_payload_history(out, {"id": 1}, history_key="history")
    append_payload_history(out, {"id": 2}, history_key="history")
    persisted = _load(out)
    assert [row["id"] for row in persisted["history"]] == [1, 2]


def test_write_json_with_diff_ledger_accepts_json_text(tmp_path: Path) -> None:
    out = tmp_path / "text_report.json"
    persisted = write_json_with_diff_ledger(out, '{"schema_version":"v1","ok":true}')
    assert persisted["ok"] is True
    assert len(persisted["diff_ledger"]) == 1


def test_write_payload_with_diff_ledger_major_diff_rollover(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    baseline = {"schema_version": "v1", "rows": [{"id": idx} for idx in range(50)]}
    write_payload_with_diff_ledger(out, baseline)
    candidate = {
        "schema_version": "v1",
        "rows": [{"id": idx + 100} for idx in range(60)],
        "new_block": [{"slot": idx, "value": idx * 2} for idx in range(30)],
    }
    persisted = write_payload_with_diff_ledger(
        out,
        candidate,
        major_diff_threshold=0.15,
        major_diff_min_paths=20,
    )
    latest = persisted["diff_ledger"][-1]
    assert latest["diff"]["churn_paths"] >= 20
    assert latest["diff"]["churn_ratio"] >= 0.15
    rollover = latest.get("major_diff_rollover") or {}
    assert rollover.get("enabled") is True
    archived = Path(str(rollover.get("archive_path")))
    assert archived.exists()


def test_write_payload_with_diff_ledger_skips_rollover_when_changed_paths_below_minimum(tmp_path: Path) -> None:
    out = tmp_path / "report_small_change.json"
    write_payload_with_diff_ledger(out, {"schema_version": "v1", "rows": [{"id": 1}]})
    persisted = write_payload_with_diff_ledger(
        out,
        {"schema_version": "v1", "rows": [{"id": 9}, {"id": 10}], "new_block": {"x": 1, "y": 2}},
        major_diff_threshold=0.2,
        major_diff_min_paths=20,
    )
    latest = persisted["diff_ledger"][-1]
    assert latest["diff"]["churn_ratio"] >= 0.2
    assert latest["diff"]["churn_paths"] < 20
    assert "major_diff_rollover" not in latest


def test_write_payload_with_diff_ledger_uses_adaptive_default_threshold(tmp_path: Path) -> None:
    out = tmp_path / "report_adaptive.json"
    small_before = {f"old_{idx}": idx for idx in range(10)}
    small_after = {f"new_{idx}": idx for idx in range(10)}
    write_payload_with_diff_ledger(out, small_before)
    persisted = write_payload_with_diff_ledger(out, small_after, major_diff_min_paths=20)
    latest = persisted["diff_ledger"][-1]
    assert latest["diff"]["paths_total_reference"] <= 250
    assert latest["diff"]["churn_paths"] >= 20
    rollover = latest.get("major_diff_rollover") or {}
    assert rollover.get("enabled") is True
    assert rollover.get("threshold") == 0.93
