from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.runtime_verification_artifact_service import (
    RuntimeVerificationArtifactContext,
    RuntimeVerificationArtifactService,
)


def _runtime_result(*, overall_evidence_class: str) -> SimpleNamespace:
    return SimpleNamespace(
        ok=False,
        checked_files=["agent_output/main.py"],
        errors=["runtime verifier failed"],
        command_results=[
            {
                "command_id": "command:001",
                "command_display": "python -m compileall -q agent_output",
                "working_directory": ".",
                "outcome": "fail",
                "returncode": 1,
                "evidence_class": "syntax_only",
            }
        ],
        failure_breakdown={"python_compile": 1},
        overall_evidence_class=overall_evidence_class,
        evidence_summary={
            "syntax_only": {
                "evaluated": True,
                "checked_files": ["agent_output/main.py"],
                "commands": [
                    {
                        "command_id": "command:001",
                        "command_display": "python -m compileall -q agent_output",
                        "working_directory": ".",
                        "outcome": "fail",
                        "returncode": 1,
                    }
                ],
            },
            "command_execution": {"evaluated": False, "commands": []},
            "behavioral_verification": {
                "evaluated": False,
                "stdout_contract_requested": False,
                "json_assertion_count": 0,
                "commands": [],
            },
            "not_evaluated": [
                {
                    "check": "behavioral_verification",
                    "reason": "no runtime stdout contract requested behavioral verification",
                }
            ],
        },
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_runtime_verification_artifact_service_preserves_record_history(tmp_path: Path) -> None:
    """Layer: contract."""
    service = RuntimeVerificationArtifactService(tmp_path)

    first = await service.write(
        context=RuntimeVerificationArtifactContext(
            run_id="run-1",
            issue_id="REV-1",
            turn_index=2,
            retry_count=0,
            seat_name="code_reviewer",
            recorded_at="2026-04-08T12:00:00+00:00",
        ),
        runtime_result=_runtime_result(overall_evidence_class="syntax_only"),
        guard_contract={"result": "fail"},
        guard_decision={"action": "retry"},
    )
    second = await service.write(
        context=RuntimeVerificationArtifactContext(
            run_id="run-1",
            issue_id="REV-1",
            turn_index=2,
            retry_count=1,
            seat_name="code_reviewer",
            recorded_at="2026-04-08T12:01:00+00:00",
        ),
        runtime_result=_runtime_result(overall_evidence_class="command_execution"),
        guard_contract={"result": "fail"},
        guard_decision={"action": "terminal_failure"},
    )

    latest_payload = _read_json(tmp_path / second.latest_path)
    index_payload = _read_json(tmp_path / second.index_path)

    assert (tmp_path / first.record_path).exists()
    assert (tmp_path / second.record_path).exists()
    assert latest_payload["provenance"]["retry_count"] == 1
    assert latest_payload["provenance"]["record_id"] == second.record_id
    assert index_payload["history_count"] == 2
    assert index_payload["latest_record_id"] == second.record_id
    assert [row["retry_count"] for row in index_payload["records"]] == [0, 1]


@pytest.mark.asyncio
async def test_runtime_verification_artifact_service_marks_support_only_semantics(tmp_path: Path) -> None:
    """Layer: contract."""
    service = RuntimeVerificationArtifactService(tmp_path)

    written = await service.write(
        context=RuntimeVerificationArtifactContext(
            run_id="run-2",
            issue_id="REV-2",
            turn_index=3,
            retry_count=0,
            seat_name="code_reviewer",
            recorded_at="2026-04-08T12:05:00+00:00",
        ),
        runtime_result=_runtime_result(overall_evidence_class="syntax_only"),
        guard_contract={"result": "fail"},
        guard_decision={"action": "retry"},
    )

    payload = _read_json(tmp_path / written.latest_path)

    assert payload["artifact_role"] == "support_verification_evidence"
    assert payload["artifact_authority"] == "support_only"
    assert payload["authored_output"] is False
    assert payload["provenance"]["run_id"] == "run-2"
    assert payload["provenance"]["issue_id"] == "REV-2"
    assert payload["provenance"]["turn_index"] == 3
    assert payload["history"]["latest_path"] == "agent_output/verification/runtime_verification.json"
    assert payload["history"]["index_path"] == "agent_output/verification/runtime_verification_index.json"
    assert payload["history"]["record_path"].endswith("/run-2/rev-2/turn_0003_retry_0000.json")
