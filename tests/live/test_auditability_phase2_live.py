from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.audit.compare_two_runs import main as compare_main
from scripts.audit.replay_turn import main as replay_main
from scripts.audit.verify_run_completeness import main as verify_main
from scripts.probes.p01_single_issue import main as p01_main
from scripts.probes.p04_odr_cards_integration import main as p04_main
from scripts.providers.check_model_provider_preflight import main as preflight_main
from tests.live.test_runtime_stability_closeout_live import _live_enabled, _live_model

pytestmark = pytest.mark.end_to_end


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_issue_id(workspace: Path, session_id: str) -> str:
    session_root = workspace / "observability" / session_id
    issue_dirs = sorted(path.name for path in session_root.iterdir() if path.is_dir() and path.name != "runtime_contracts")
    if not issue_dirs:
        raise AssertionError(f"No issue directories found under {session_root}")
    return issue_dirs[0]


def _run_legacy_main(monkeypatch: pytest.MonkeyPatch, main_func: object, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", argv)
    return int(main_func())


def test_phase2_auditability_live_suite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: end-to-end. Verifies the Phase 2 audit operators run against live cards and ODR probe workspaces."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live Phase 2 auditability proof.")

    model_id = _live_model()
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")

    preflight_code = _run_legacy_main(
        monkeypatch,
        preflight_main,
        [
            "check_model_provider_preflight.py",
            "--provider",
            "ollama",
            "--model-id",
            model_id,
            "--smoke-stream",
        ],
    )
    assert preflight_code == 0

    compare_a_workspace = tmp_path / "compare_a"
    compare_b_workspace = tmp_path / "compare_b"
    compare_a_probe = tmp_path / "reports" / "p01_compare_a.json"
    compare_b_probe = tmp_path / "reports" / "p01_compare_b.json"
    odr_probe = tmp_path / "reports" / "p04_odr.json"

    assert (
        p01_main(
            [
                "--workspace",
                str(compare_a_workspace),
                "--execution-profile",
                "builder_guard_app_v1",
                "--artifact-path",
                "agent_output/main.py",
                "--model",
                model_id,
                "--output",
                str(compare_a_probe),
                "--json",
            ]
        )
        == 0
    )
    assert (
        p01_main(
            [
                "--workspace",
                str(compare_b_workspace),
                "--execution-profile",
                "builder_guard_app_v1",
                "--artifact-path",
                "agent_output/main.py",
                "--model",
                model_id,
                "--output",
                str(compare_b_probe),
                "--json",
            ]
        )
        == 0
    )
    p04_exit = p04_main(
        [
            "--workspace",
            str(tmp_path / "odr_workspace"),
            "--model",
            model_id,
            "--output",
            str(odr_probe),
            "--json",
        ]
    )
    assert p04_exit in {0, 1}

    compare_a_payload = _load_json(compare_a_probe)
    compare_b_payload = _load_json(compare_b_probe)
    odr_payload = _load_json(odr_probe)
    assert compare_a_payload["probe_status"] == "observed"
    assert compare_b_payload["probe_status"] == "observed"
    assert odr_payload["probe_status"] == "observed"
    if p04_exit == 0:
        assert odr_payload["observed_result"] == "success"
    else:
        assert odr_payload["observed_result"] == "failure"
        assert odr_payload["variants"]["odr"]["run_summary"]["status"] in {"failed", "terminal_failure"}
        assert odr_payload["variants"]["odr"]["run_summary"].get("odr_active") is True

    verify_cards_output = tmp_path / "reports" / "verify_cards.json"
    verify_odr_output = tmp_path / "reports" / "verify_odr.json"
    assert (
        verify_main(
            [
                "--workspace",
                str(compare_a_workspace),
                "--session-id",
                str(compare_a_payload["session_id"]),
                "--output",
                str(verify_cards_output),
                "--json",
            ]
        )
        == 0
    )
    verify_odr_exit = verify_main(
        [
            "--workspace",
            str(odr_payload["variants"]["odr"]["workspace"]),
            "--session-id",
            str(odr_payload["variants"]["odr"]["session_id"]),
            "--output",
            str(verify_odr_output),
            "--json",
        ]
    )
    assert verify_odr_exit in {0, 1}

    cards_verify = _load_json(verify_cards_output)
    odr_verify = _load_json(verify_odr_output)
    assert cards_verify["mar_complete"] is True
    if verify_odr_exit == 0:
        assert odr_verify["mar_complete"] is True
        assert odr_payload["variants"]["odr"]["run_summary"].get("odr_artifact_path")
    else:
        assert odr_verify["mar_complete"] is False
        if odr_payload["observed_result"] == "success":
            assert any(
                token in set(odr_verify["missing_evidence"])
                for token in {
                    "no_authoritative_authored_outputs_named",
                    "no_authoritative_contract_verdict_surface",
                }
            )
        else:
            assert odr_payload["variants"]["odr"]["run_summary"]["status"] in {"failed", "terminal_failure"}

    compare_output = tmp_path / "reports" / "compare_runs.json"
    compare_exit = compare_main(
        [
            "--workspace-a",
            str(compare_a_workspace),
            "--session-id-a",
            str(compare_a_payload["session_id"]),
            "--workspace-b",
            str(compare_b_workspace),
            "--session-id-b",
            str(compare_b_payload["session_id"]),
            "--output",
            str(compare_output),
            "--json",
        ]
    )
    assert compare_exit in {0, 1}
    compare_payload = _load_json(compare_output)
    assert compare_payload["verdict"] in {"stable", "diverged"}
    assert compare_payload["compared_surfaces"]

    replay_output = tmp_path / "reports" / "replay_turn.json"
    replay_issue_id = _first_issue_id(compare_a_workspace, str(compare_a_payload["session_id"]))
    replay_exit = replay_main(
        [
            "--workspace",
            str(compare_a_workspace),
            "--session-id",
            str(compare_a_payload["session_id"]),
            "--issue-id",
            replay_issue_id,
            "--turn-index",
            "1",
            "--role",
            "coder",
            "--output",
            str(replay_output),
            "--json",
        ]
    )
    assert replay_exit in {0, 1}
    replay_payload = _load_json(replay_output)
    assert replay_payload["stability_status"] in {"stable", "diverged", "blocked"}
    if replay_payload["stability_status"] == "blocked":
        assert replay_payload["error"]
    else:
        assert replay_payload["structural_verdict"]["replayed_sha256"]

    print(
        "[live][auditability-phase2] "
        f"model={model_id} "
        f"cards_mar={cards_verify['mar_complete']} "
        f"odr_mar={odr_verify['mar_complete']} "
        f"compare={compare_payload['verdict']} "
        f"replay={replay_payload['stability_status']}"
    )
