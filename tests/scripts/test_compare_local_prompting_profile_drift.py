from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.compare_local_prompting_profile_drift import main


def _snapshot(profile_id: str) -> dict[str, object]:
    return {
        "schema_version": "local_prompt_profiles.v1",
        "profiles": [
            {
                "provider": "ollama",
                "match": {"model_contains": ["qwen"]},
                "profile": {"profile_id": profile_id, "template_family": "chatml"},
            }
        ],
    }


def test_compare_local_prompting_profile_drift_detects_change(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    out = tmp_path / "drift.json"
    before.write_text(json.dumps(_snapshot("ollama.qwen.v1")), encoding="utf-8")
    after.write_text(json.dumps(_snapshot("ollama.qwen.v2")), encoding="utf-8")

    exit_code = main(["--before", str(before), "--after", str(after), "--out", str(out), "--strict"])
    assert exit_code == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["changed"] is True
    assert payload["added_profiles"] == ["ollama.qwen.v2"]
    assert payload["removed_profiles"] == ["ollama.qwen.v1"]


def test_compare_local_prompting_profile_drift_handles_no_change(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    out = tmp_path / "drift.json"
    snapshot = _snapshot("ollama.qwen.v1")
    before.write_text(json.dumps(snapshot), encoding="utf-8")
    after.write_text(json.dumps(snapshot), encoding="utf-8")

    exit_code = main(["--before", str(before), "--after", str(after), "--out", str(out), "--strict"])
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["changed"] is False
