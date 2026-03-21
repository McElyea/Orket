from __future__ import annotations

from pathlib import Path

import pytest

from scripts.probes import p04_odr_cards_integration as p04

pytestmark = pytest.mark.unit


def test_default_probe_ids_include_unique_variant_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Uuid:
        hex = "abc123def4567890fedcba"

    monkeypatch.setattr(p04.uuid, "uuid4", lambda: _Uuid())
    token = p04._variant_token(Path("C:/tmp/p04-proof"))

    assert token == "p04-proof-abc123def4"
    args = p04._parse_args([])
    assert p04._issue_id(variant_token=token, label="odr") == "odr-p04-proof-abc123def4-issue"
    assert p04._session_id(args, variant_token=token, label="odr") == (
        "probe-p04-odr-cards-integration-p04-proof-abc123def4-odr"
    )
    assert p04._build_id(args, variant_token=token, label="odr") == (
        "build-probe-p04-odr-cards-integration-p04-proof-abc123def4-odr"
    )


def test_issue_payload_includes_probe_odr_max_rounds_when_requested() -> None:
    payload = p04._issue_payload(
        issue_id="ISSUE-1",
        execution_profile=p04.ODR_EXECUTION_PROFILE,
        artifact_path="agent_output/p04_odr.py",
        odr_max_rounds=1,
    )

    assert payload["params"]["odr_max_rounds"] == 1


def test_observed_result_rejects_terminal_odr_prebuild_failure() -> None:
    result = p04._observed_result(
        {
            "run_summary": {
                "status": "done",
                "stop_reason": "completed",
                "odr_active": False,
            }
        },
        {
            "run_summary": {
                "status": "terminal_failure",
                "stop_reason": "terminal_failure",
                "odr_active": True,
                "odr_artifact_path": "observability/run/ISSUE/odr_refinement.json",
            },
            "odr_artifact": {"accepted": False},
        },
    )

    assert result == "failure"


def test_observed_result_requires_successful_odr_continuation() -> None:
    result = p04._observed_result(
        {
            "run_summary": {
                "status": "done",
                "stop_reason": "completed",
                "odr_active": False,
            }
        },
        {
            "run_summary": {
                "status": "done",
                "stop_reason": "completed",
                "odr_active": True,
                "odr_artifact_path": "observability/run/ISSUE/odr_refinement.json",
            },
            "odr_artifact": {"accepted": True},
        },
    )

    assert result == "success"


def test_main_returns_failure_for_observed_probe_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _fake_run_probe(_args):
        return {
            "schema_version": "phase1_probe.p04.v2",
            "probe_id": "P-04",
            "probe_status": "observed",
            "observed_result": "failure",
        }

    monkeypatch.setattr(p04, "_run_probe", _fake_run_probe)
    monkeypatch.setattr(p04, "write_report", lambda _path, payload: payload)

    exit_code = p04.main(["--output", str(tmp_path / "out.json")])

    assert exit_code == 1
