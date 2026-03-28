from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.check_protocol_enforce_cutover_readiness import main


def _write_manifest(
    path: Path,
    *,
    window_id: str,
    status: str,
    signoff_pass: bool,
    failed_steps: list[str] | None = None,
    parity_invalid_projection_field_counts: dict[str, dict[str, int]] | None = None,
    rollout_parity_invalid_projection_field_counts: dict[str, dict[str, int]] | None = None,
) -> None:
    payload = {
        "schema_version": "protocol_enforce_window_capture_manifest.v1",
        "window": {"id": window_id, "date": "2026-03-06"},
        "status": status,
        "failed_steps": list(failed_steps or []),
        "signoff": {
            "all_gates_passed": signoff_pass,
            "gate_status": "PASS" if signoff_pass else "FAIL",
            "parity_invalid_projection_field_counts": dict(parity_invalid_projection_field_counts or {}),
            "rollout_parity_invalid_projection_field_counts": dict(
                rollout_parity_invalid_projection_field_counts or {}
            ),
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_check_protocol_enforce_cutover_readiness_passes_with_two_distinct_windows(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "readiness.json"
    _write_manifest(a, window_id="window_a", status="PASS", signoff_pass=True)
    _write_manifest(b, window_id="window_b", status="PASS", signoff_pass=True)

    exit_code = main(["--manifest", str(a), "--manifest", str(b), "--out", str(out), "--strict"])
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ready"] is True
    assert payload["passing_windows"] == 2


def test_check_protocol_enforce_cutover_readiness_strict_fails_on_failed_window(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_manifest(a, window_id="window_a", status="PASS", signoff_pass=True)
    _write_manifest(b, window_id="window_b", status="FAIL", signoff_pass=False, failed_steps=["ledger_parity_campaign"])

    exit_code = main(["--manifest", str(a), "--manifest", str(b), "--strict"])
    assert exit_code == 1


def test_check_protocol_enforce_cutover_readiness_enforces_distinct_window_ids_by_default(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _write_manifest(a, window_id="window_x", status="PASS", signoff_pass=True)
    _write_manifest(b, window_id="window_x", status="PASS", signoff_pass=True)

    exit_code = main(["--manifest", str(a), "--manifest", str(b), "--strict"])
    assert exit_code == 1

    exit_code_relaxed = main(
        [
            "--manifest",
            str(a),
            "--manifest",
            str(b),
            "--no-require-distinct-window-ids",
            "--strict",
        ]
    )
    assert exit_code_relaxed == 0


def test_check_protocol_enforce_cutover_readiness_preserves_invalid_projection_counts(tmp_path: Path) -> None:
    """contract: cutover readiness keeps signoff invalid-projection detail per window and in aggregate."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "readiness.json"
    _write_manifest(a, window_id="window_a", status="PASS", signoff_pass=True)
    _write_manifest(
        b,
        window_id="window_b",
        status="FAIL",
        signoff_pass=False,
        failed_steps=["record_window_signoff"],
        parity_invalid_projection_field_counts={"sqlite": {"artifact_json": 1, "summary_json": 1}},
        rollout_parity_invalid_projection_field_counts={"sqlite": {"summary_json": 1}},
    )

    exit_code = main(["--manifest", str(a), "--manifest", str(b), "--out", str(out)])
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["windows_with_invalid_projection_counts"] == 1
    assert payload["parity_invalid_projection_field_counts"]["sqlite"] == {
        "artifact_json": 1,
        "summary_json": 1,
    }
    assert payload["rollout_parity_invalid_projection_field_counts"]["sqlite"] == {"summary_json": 1}
    assert payload["windows"][1]["parity_invalid_projection_field_counts"]["sqlite"] == {
        "artifact_json": 1,
        "summary_json": 1,
    }
    assert payload["windows"][1]["rollout_parity_invalid_projection_field_counts"]["sqlite"] == {
        "summary_json": 1
    }
