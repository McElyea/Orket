# Layer: contract
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.common.run_summary_support import load_first_validated_run_summary, load_validated_run_summary


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


@pytest.mark.contract
def test_load_validated_run_summary_accepts_projection_framed_payload(tmp_path: Path) -> None:
    path = tmp_path / "run_summary.json"
    _write_json(
        path,
        {
            "run_id": "run-valid",
            "status": "done",
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": None,
            "truthful_runtime_packet1": {
                "projection_source": "packet1_facts",
                "projection_only": True,
            },
        },
    )

    payload = load_validated_run_summary(path)

    assert payload["run_id"] == "run-valid"


@pytest.mark.contract
def test_load_first_validated_run_summary_skips_invalid_candidates(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid" / "run_summary.json"
    valid = tmp_path / "valid" / "run_summary.json"
    _write_json(
        invalid,
        {
            "run_id": "run-invalid",
            "status": "done",
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": None,
            "truthful_runtime_packet1": {
                "projection_source": "legacy_packet1_surface",
                "projection_only": True,
            },
        },
    )
    _write_json(
        valid,
        {
            "run_id": "run-valid",
            "status": "done",
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": None,
            "truthful_runtime_packet1": {
                "projection_source": "packet1_facts",
                "projection_only": True,
            },
        },
    )

    payload = load_first_validated_run_summary([invalid, valid])

    assert payload is not None
    assert payload["run_id"] == "run-valid"
