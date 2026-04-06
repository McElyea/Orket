# LIFECYCLE: one-shot
from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.record_protocol_enforce_window_signoff import main


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_record_protocol_enforce_window_signoff_passes_on_clean_inputs(tmp_path: Path) -> None:
    replay = tmp_path / "replay.json"
    parity = tmp_path / "parity.json"
    rollout = tmp_path / "rollout.json"
    summary = tmp_path / "summary.json"
    out = tmp_path / "signoff.json"
    _write(replay, {"all_match": True})
    _write(parity, {"all_match": True})
    _write(rollout, {"strict_ok": True, "schema_version": "protocol_rollout_bundle.v1"})
    _write(summary, {"unregistered_count": 0, "family_counts": {}})

    exit_code = main(
        [
            "--window-id",
            "window_a",
            "--window-date",
            "2026-03-05",
            "--replay-campaign",
            str(replay),
            "--parity-campaign",
            str(parity),
            "--rollout-bundle",
            str(rollout),
            "--error-summary",
            str(summary),
            "--retry-spike-status",
            "pass",
            "--approver",
            "Orket Core",
            "--out",
            str(out),
            "--strict",
        ]
    )
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["gate_status"] == "PASS"
    assert payload["all_gates_passed"] is True
    assert payload["gates"]["retry_spike_check"]["passed"] is True


def test_record_protocol_enforce_window_signoff_strict_fails_when_retry_unknown(tmp_path: Path) -> None:
    replay = tmp_path / "replay.json"
    parity = tmp_path / "parity.json"
    rollout = tmp_path / "rollout.json"
    summary = tmp_path / "summary.json"
    _write(replay, {"all_match": True})
    _write(parity, {"all_match": True})
    _write(rollout, {"strict_ok": True, "schema_version": "protocol_rollout_bundle.v1"})
    _write(summary, {"unregistered_count": 0, "family_counts": {}})

    exit_code = main(
        [
            "--window-id",
            "window_b",
            "--window-date",
            "2026-03-05",
            "--replay-campaign",
            str(replay),
            "--parity-campaign",
            str(parity),
            "--rollout-bundle",
            str(rollout),
            "--error-summary",
            str(summary),
            "--retry-spike-status",
            "unknown",
            "--approver",
            "Orket Core",
            "--strict",
        ]
    )
    assert exit_code == 1


def test_record_protocol_enforce_window_signoff_blocks_unapproved_error_families(tmp_path: Path) -> None:
    replay = tmp_path / "replay.json"
    parity = tmp_path / "parity.json"
    rollout = tmp_path / "rollout.json"
    summary = tmp_path / "summary.json"
    _write(replay, {"all_match": True})
    _write(parity, {"all_match": True})
    _write(rollout, {"strict_ok": True, "schema_version": "protocol_rollout_bundle.v1"})
    _write(summary, {"unregistered_count": 0, "family_counts": {"E_PARSE_JSON": 2}})

    exit_code = main(
        [
            "--window-id",
            "window_c",
            "--window-date",
            "2026-03-05",
            "--replay-campaign",
            str(replay),
            "--parity-campaign",
            str(parity),
            "--rollout-bundle",
            str(rollout),
            "--error-summary",
            str(summary),
            "--retry-spike-status",
            "pass",
            "--approver",
            "Orket Core",
            "--strict",
        ]
    )
    assert exit_code == 1


def test_record_protocol_enforce_window_signoff_preserves_invalid_projection_counts(tmp_path: Path) -> None:
    replay = tmp_path / "replay.json"
    parity = tmp_path / "parity.json"
    rollout = tmp_path / "rollout.json"
    summary = tmp_path / "summary.json"
    out = tmp_path / "signoff.json"
    _write(replay, {"all_match": True})
    _write(
        parity,
        {
            "all_match": False,
            "compatibility_telemetry_delta": {
                "sqlite_invalid_projection_field_counts": {"artifact_json": 1, "summary_json": 1},
                "protocol_invalid_projection_field_counts": {},
            },
        },
    )
    _write(
        rollout,
        {
            "strict_ok": False,
            "schema_version": "protocol_rollout_bundle.v1",
            "ledger_parity_campaign": {
                "compatibility_telemetry_delta": {
                    "sqlite_invalid_projection_field_counts": {"artifact_json": 1, "summary_json": 1},
                    "protocol_invalid_projection_field_counts": {},
                }
            },
        },
    )
    _write(summary, {"unregistered_count": 0, "family_counts": {}})

    exit_code = main(
        [
            "--window-id",
            "window_d",
            "--window-date",
            "2026-03-05",
            "--replay-campaign",
            str(replay),
            "--parity-campaign",
            str(parity),
            "--rollout-bundle",
            str(rollout),
            "--error-summary",
            str(summary),
            "--retry-spike-status",
            "pass",
            "--approver",
            "Orket Core",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["parity_invalid_projection_field_counts"]["sqlite"] == {"artifact_json": 1, "summary_json": 1}
    assert payload["rollout_parity_invalid_projection_field_counts"]["sqlite"] == {
        "artifact_json": 1,
        "summary_json": 1,
    }
    assert "sqlite_invalid_projection_field_counts={'artifact_json': 1, 'summary_json': 1}" in payload["gates"][
        "parity_all_match"
    ]["detail"]
