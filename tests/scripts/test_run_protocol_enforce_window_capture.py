from __future__ import annotations

import json
from pathlib import Path

import scripts.protocol.run_protocol_enforce_window_capture as capture_script


def _value_after(argv: list[str], flag: str) -> str:
    index = argv.index(flag)
    return str(argv[index + 1])


def test_run_protocol_enforce_window_capture_writes_manifest_and_passes(tmp_path: Path, monkeypatch) -> None:
    out_root = tmp_path / "window_x"

    def _determinism(argv: list[str] | None = None) -> int:
        out = Path(_value_after(list(argv or []), "--out"))
        out.write_text(json.dumps({"all_match": True}) + "\n", encoding="utf-8")
        return 0

    def _parity(argv: list[str] | None = None) -> int:
        out = Path(_value_after(list(argv or []), "--out"))
        out.write_text(json.dumps({"all_match": True}) + "\n", encoding="utf-8")
        return 0

    def _publish(argv: list[str] | None = None) -> int:
        out_dir = Path(_value_after(list(argv or []), "--out-dir"))
        out_dir.mkdir(parents=True, exist_ok=True)
        latest = out_dir / "protocol_rollout_bundle.latest.json"
        latest.write_text(json.dumps({"strict_ok": True}) + "\n", encoding="utf-8")
        return 0

    def _summary(argv: list[str] | None = None) -> int:
        out = Path(_value_after(list(argv or []), "--out"))
        out.write_text(json.dumps({"unregistered_count": 0, "family_counts": {}}) + "\n", encoding="utf-8")
        return 0

    def _signoff(argv: list[str] | None = None) -> int:
        out = Path(_value_after(list(argv or []), "--out"))
        out.write_text(json.dumps({"all_gates_passed": True, "gate_status": "PASS"}) + "\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(capture_script, "run_determinism_campaign_main", _determinism)
    monkeypatch.setattr(capture_script, "run_ledger_parity_campaign_main", _parity)
    monkeypatch.setattr(capture_script, "publish_rollout_artifacts_main", _publish)
    monkeypatch.setattr(capture_script, "summarize_error_codes_main", _summary)
    monkeypatch.setattr(capture_script, "record_window_signoff_main", _signoff)

    exit_code = capture_script.main(
        [
            "--window-id",
            "window_x",
            "--window-date",
            "2026-03-06",
            "--workspace-root",
            str(tmp_path),
            "--run-id",
            "run-x",
            "--retry-spike-status",
            "pass",
            "--approver",
            "ops",
            "--out-root",
            str(out_root),
            "--strict",
        ]
    )
    assert exit_code == 0
    manifest = json.loads((out_root / "protocol_window_capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PASS"
    assert len(manifest["steps"]) == 5
    assert manifest["failed_steps"] == []


def test_run_protocol_enforce_window_capture_fails_when_step_fails(tmp_path: Path, monkeypatch) -> None:
    out_root = tmp_path / "window_fail"

    def _ok(argv: list[str] | None = None) -> int:
        if "--out" in list(argv or []):
            out = Path(_value_after(list(argv or []), "--out"))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"all_match": True}) + "\n", encoding="utf-8")
        if "--out-dir" in list(argv or []):
            out_dir = Path(_value_after(list(argv or []), "--out-dir"))
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "protocol_rollout_bundle.latest.json").write_text(json.dumps({"strict_ok": True}) + "\n", encoding="utf-8")
        return 0

    def _fail(argv: list[str] | None = None) -> int:
        return 1

    monkeypatch.setattr(capture_script, "run_determinism_campaign_main", _ok)
    monkeypatch.setattr(capture_script, "run_ledger_parity_campaign_main", _fail)
    monkeypatch.setattr(capture_script, "publish_rollout_artifacts_main", _ok)
    monkeypatch.setattr(capture_script, "summarize_error_codes_main", _ok)
    monkeypatch.setattr(capture_script, "record_window_signoff_main", _ok)

    exit_code = capture_script.main(
        [
            "--window-id",
            "window_fail",
            "--window-date",
            "2026-03-06",
            "--workspace-root",
            str(tmp_path),
            "--run-id",
            "run-fail",
            "--retry-spike-status",
            "pass",
            "--approver",
            "ops",
            "--out-root",
            str(out_root),
            "--strict",
        ]
    )
    assert exit_code == 1
    manifest = json.loads((out_root / "protocol_window_capture_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "FAIL"
    assert "ledger_parity_campaign" in manifest["failed_steps"]


def test_run_protocol_enforce_window_capture_defaults_session_id_to_run_id(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, list[str]] = {}

    def _determinism(argv: list[str] | None = None) -> int:
        seen["determinism"] = list(argv or [])
        out = Path(_value_after(seen["determinism"], "--out"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"all_match": True}) + "\n", encoding="utf-8")
        return 0

    def _parity(argv: list[str] | None = None) -> int:
        seen["parity"] = list(argv or [])
        out = Path(_value_after(seen["parity"], "--out"))
        out.write_text(json.dumps({"all_match": True}) + "\n", encoding="utf-8")
        return 0

    def _publish(argv: list[str] | None = None) -> int:
        seen["publish"] = list(argv or [])
        out_dir = Path(_value_after(seen["publish"], "--out-dir"))
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "protocol_rollout_bundle.latest.json").write_text(json.dumps({"strict_ok": True}) + "\n", encoding="utf-8")
        return 0

    def _summary(argv: list[str] | None = None) -> int:
        out = Path(_value_after(list(argv or []), "--out"))
        out.write_text(json.dumps({"unregistered_count": 0, "family_counts": {}}) + "\n", encoding="utf-8")
        return 0

    def _signoff(argv: list[str] | None = None) -> int:
        out = Path(_value_after(list(argv or []), "--out"))
        out.write_text(json.dumps({"all_gates_passed": True, "gate_status": "PASS"}) + "\n", encoding="utf-8")
        return 0

    monkeypatch.setattr(capture_script, "run_determinism_campaign_main", _determinism)
    monkeypatch.setattr(capture_script, "run_ledger_parity_campaign_main", _parity)
    monkeypatch.setattr(capture_script, "publish_rollout_artifacts_main", _publish)
    monkeypatch.setattr(capture_script, "summarize_error_codes_main", _summary)
    monkeypatch.setattr(capture_script, "record_window_signoff_main", _signoff)

    exit_code = capture_script.main(
        [
            "--window-id",
            "window_default",
            "--window-date",
            "2026-03-06",
            "--workspace-root",
            str(tmp_path),
            "--run-id",
            "run-default",
            "--retry-spike-status",
            "pass",
            "--approver",
            "ops",
        ]
    )
    assert exit_code == 0
    assert _value_after(seen["parity"], "--session-id") == "run-default"
    assert _value_after(seen["publish"], "--session-id") == "run-default"
    assert _value_after(seen["determinism"], "--baseline-run-id") == "run-default"
