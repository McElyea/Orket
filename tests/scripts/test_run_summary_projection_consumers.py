# Layer: contract
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.probes.probe_support import run_summary
from scripts.training.extract_training_data import extract_from_workspace


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


@pytest.mark.contract
def test_probe_support_run_summary_rejects_untrusted_projection(tmp_path: Path) -> None:
    session_id = "sess-probe"
    _write_json(
        tmp_path / "runs" / session_id / "run_summary.json",
        {
            "run_id": session_id,
            "status": "done",
            "artifact_ids": [],
            "failure_reason": None,
            "control_plane": {
                "projection_source": "legacy_cards_summary",
                "projection_only": True,
            },
        },
    )

    payload = run_summary(tmp_path, session_id)

    assert payload == {}


@pytest.mark.contract
def test_extract_training_data_rejects_untrusted_run_summary_projection(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    run_id = "run-training"
    _write_json(
        workspace / run_id / "runs" / run_id / "run_summary.json",
        {
            "run_id": run_id,
            "status": "done",
            "artifact_ids": [],
            "failure_reason": None,
            "control_plane": {
                "projection_source": "legacy_cards_summary",
                "projection_only": True,
            },
        },
    )

    examples, stats = extract_from_workspace(workspace)

    assert examples == []
    assert stats.runs_scanned == 1
    assert stats.runs_accepted == 0
    assert stats.runs_rejected_no_summary == 1
