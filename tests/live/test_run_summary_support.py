from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live.run_summary_support import read_validated_run_summary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(payload).encode("utf-8"))


def test_read_validated_run_summary_accepts_projection_markers(tmp_path: Path) -> None:
    """Layer: unit. Validated live-proof helpers should accept correctly framed projection-backed summaries."""
    path = tmp_path / "run_summary.json"
    _write_json(
        path,
        {
            "run_id": "sess-live-valid",
            "status": "done",
            "duration_ms": 1,
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": None,
            "truthful_runtime_packet1": {
                "projection_source": "packet1_facts",
                "projection_only": True,
            },
        },
    )

    payload = read_validated_run_summary(path)

    assert payload["run_id"] == "sess-live-valid"


def test_read_validated_run_summary_rejects_drifted_projection_markers(tmp_path: Path) -> None:
    """Layer: unit. Validated live-proof helpers should fail closed on malformed projection framing."""
    path = tmp_path / "run_summary.json"
    _write_json(
        path,
        {
            "run_id": "sess-live-invalid",
            "status": "done",
            "duration_ms": 1,
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": None,
            "truthful_runtime_packet1": {
                "projection_source": "legacy_packet1_surface",
                "projection_only": True,
            },
        },
    )

    with pytest.raises(ValueError, match="run_summary_truthful_runtime_packet1_projection_source_invalid"):
        read_validated_run_summary(path)


def test_read_validated_run_summary_rejects_degraded_payload(tmp_path: Path) -> None:
    """Layer: unit. Live-proof helpers should fail closed on degraded summaries."""
    path = tmp_path / "run_summary.json"
    _write_json(
        path,
        {
            "run_id": "sess-live-degraded",
            "status": "failed",
            "duration_ms": 1,
            "tools_used": [],
            "artifact_ids": [],
            "failure_reason": "summary_generation_failed",
            "is_degraded": True,
        },
    )

    with pytest.raises(ValueError, match="live_run_summary_degraded"):
        read_validated_run_summary(path)
