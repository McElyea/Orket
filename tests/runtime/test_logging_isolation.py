from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.logging import log_event


def _read_log_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.strip()
        if not token:
            continue
        rows.append(json.loads(token))
    return rows


def test_log_event_isolates_interleaved_workspace_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    workspace_a = tmp_path / "workspace_a"
    workspace_b = tmp_path / "workspace_b"

    for index in range(5):
        log_event("event_a", {"seq": index}, workspace=workspace_a)
        log_event("event_b", {"seq": index}, workspace=workspace_b)

    records_a = _read_log_records(workspace_a / "orket.log")
    records_b = _read_log_records(workspace_b / "orket.log")

    assert len(records_a) == 5
    assert len(records_b) == 5
    assert all(str(row.get("event")) == "event_a" for row in records_a)
    assert all(str(row.get("event")) == "event_b" for row in records_b)
    assert all("logging_context_mode" not in dict(row.get("data") or {}) for row in records_a + records_b)


def test_log_event_missing_workspace_fail_fast_has_stable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_LOGGING_MISSING_CONTEXT_MODE", "fail_fast")

    with pytest.raises(RuntimeError, match="E_LOG_WORKSPACE_REQUIRED"):
        log_event("event_missing_workspace", {"ok": False})


def test_log_event_missing_workspace_legacy_mode_writes_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_LOGGING_MISSING_CONTEXT_MODE", "legacy_default")

    log_event("event_legacy_fallback", {"ok": True})
    records = _read_log_records(tmp_path / "workspace" / "default" / "orket.log")
    assert records
    marker_data = dict(records[-1].get("data") or {})
    assert marker_data["logging_context_mode"] == "legacy_default"
    assert marker_data["logging_context_marker"] == "workspace_default_fallback"
