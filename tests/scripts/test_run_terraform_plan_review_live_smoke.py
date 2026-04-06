# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.reviewrun.run_terraform_plan_review_live_smoke import main


def _load_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


# Layer: contract
def test_run_terraform_plan_review_live_smoke_marks_missing_env_as_environment_blocker(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "terraform_plan_review_live_smoke.json"
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_S3_URI", raising=False)
    monkeypatch.delenv("ORKET_TERRAFORM_PLAN_REVIEW_SMOKE_MODEL_ID", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)

    exit_code = main(["--out", str(out)])
    payload = _load_json(out)

    assert exit_code == 1
    assert payload["status"] == "blocked"
    assert payload["path"] == "blocked"
    assert payload["result"] == "environment blocker"
    assert payload["publish_decision"] == "no_publish"
    assert payload["execution_status"] == "environment_blocker"
    assert payload["reason"].startswith("missing_required_env:")
    assert "diff_ledger" in payload
