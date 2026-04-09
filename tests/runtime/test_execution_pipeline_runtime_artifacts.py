from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.runtime.execution.execution_pipeline_runtime_artifacts import ExecutionPipelineRuntimeArtifactsMixin

pytestmark = pytest.mark.integration


class _Harness(ExecutionPipelineRuntimeArtifactsMixin):
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.async_cards = object()


def _cards_artifacts(*, workload: str = "cards-runtime") -> dict[str, object]:
    return {
        "run_identity": {
            "run_id": "sess-cards-runtime-artifacts",
            "workload": workload,
            "start_time": "2036-03-05T12:00:00+00:00",
            "identity_scope": "session_bootstrap",
            "projection_source": "session_bootstrap_artifacts",
            "projection_only": True,
        }
    }


@pytest.mark.asyncio
async def test_resolve_cards_runtime_artifacts_reports_log_missing_for_cards_workload(tmp_path: Path) -> None:
    """Layer: integration. Verifies cards-runtime extraction reports `log_missing` instead of disappearing."""
    harness = _Harness(tmp_path)

    payload = await harness._resolve_cards_runtime_artifacts(
        artifacts=_cards_artifacts(),
        run_id="sess-cards-runtime-artifacts",
        session_status="failed",
        failure_reason="log_missing",
    )

    assert payload == {
        "cards_runtime_facts": {
            "resolution_state": "log_missing",
        }
    }


@pytest.mark.asyncio
async def test_resolve_cards_runtime_artifacts_reports_no_events_found_for_cards_workload(tmp_path: Path) -> None:
    """Layer: integration. Verifies an empty cards-runtime log reports `no_events_found` explicitly."""
    harness = _Harness(tmp_path)
    (tmp_path / "orket.log").write_text("", encoding="utf-8")

    payload = await harness._resolve_cards_runtime_artifacts(
        artifacts=_cards_artifacts(),
        run_id="sess-cards-runtime-artifacts",
        session_status="failed",
        failure_reason="no_events",
    )

    assert payload == {
        "cards_runtime_facts": {
            "resolution_state": "no_events_found",
        }
    }


@pytest.mark.asyncio
async def test_resolve_cards_runtime_artifacts_reports_resolution_failed_on_read_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: integration. Verifies log read failures remain machine-readable as `resolution_failed`."""
    harness = _Harness(tmp_path)
    (tmp_path / "orket.log").write_text("{}", encoding="utf-8")

    def _boom(*_args, **_kwargs):
        raise OSError("denied")

    monkeypatch.setattr("orket.runtime.execution.execution_pipeline_runtime_artifacts.aiofiles.open", _boom)

    payload = await harness._resolve_cards_runtime_artifacts(
        artifacts=_cards_artifacts(),
        run_id="sess-cards-runtime-artifacts",
        session_status="failed",
        failure_reason="read_error",
    )

    assert payload["cards_runtime_facts"]["resolution_state"] == "resolution_failed"
    assert payload["cards_runtime_facts"]["resolution_error"] == {
        "error_type": "OSError",
        "error": "denied",
    }


@pytest.mark.asyncio
async def test_resolve_cards_runtime_artifacts_marks_resolved_when_runtime_events_exist(tmp_path: Path) -> None:
    """Layer: integration. Verifies cards-runtime extraction stays truthful when ODR events are present."""
    harness = _Harness(tmp_path)
    (tmp_path / "orket.log").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "odr_prebuild_completed",
                        "data": {
                            "session_id": "sess-cards-runtime-artifacts",
                            "issue_id": "ISSUE-1",
                            "execution_profile": "odr_prebuild_builder_guard_v1",
                            "odr_active": True,
                            "audit_mode": "independent",
                            "odr_valid": True,
                            "odr_pending_decisions": 0,
                            "odr_stop_reason": "STABLE_DIFF_FLOOR",
                            "odr_artifact_path": "observability/sess-cards-runtime-artifacts/ISSUE-1/odr_refinement.json",
                            "last_valid_round_index": 2,
                            "last_emitted_round_index": 3,
                        },
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = await harness._resolve_cards_runtime_artifacts(
        artifacts=_cards_artifacts(),
        run_id="sess-cards-runtime-artifacts",
        session_status="done",
        failure_reason=None,
    )

    facts = payload["cards_runtime_facts"]
    assert facts["resolution_state"] == "resolved"
    assert facts["execution_profile"] == "odr_prebuild_builder_guard_v1"
    assert facts["audit_mode"] == "independent"
    assert facts["last_valid_round_index"] == 2
    assert facts["last_emitted_round_index"] == 3
    assert facts["stop_reason"] == "completed"
