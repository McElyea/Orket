from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _artifact_files(root: Path) -> list[Path]:
    artifacts_root = root / ".orket" / "replay_artifacts"
    if not artifacts_root.exists():
        return []
    return sorted(path for path in artifacts_root.rglob("*.json") if path.is_file())


def test_replay_artifact_recording_disabled_by_default(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    code = main(["init", "minimal-node", "demo", "--dir", str(tmp_path / "demo"), "--json"])
    _ = capsys.readouterr()
    assert code == 0
    assert _artifact_files(tmp_path) == []


def test_replay_artifact_recording_writes_artifact_when_enabled(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_REPLAY_ARTIFACTS", "1")

    code = main(["init", "minimal-node", "demo", "--dir", str(tmp_path / "demo"), "--json"])
    _ = capsys.readouterr()
    assert code == 0

    artifacts = _artifact_files(tmp_path)
    assert len(artifacts) == 1
    payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert payload["contract_version"] == "core_pillars/replay_artifact/v1"
    assert payload["command"] == "init"
    assert payload["result"]["ok"] is True
    assert isinstance(payload["artifact_id"], str) and len(payload["artifact_id"]) == 64
