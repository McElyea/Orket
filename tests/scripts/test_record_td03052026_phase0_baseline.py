# LIFECYCLE: one-shot
from __future__ import annotations

import json
from pathlib import Path

from scripts.techdebt.record_td03052026_phase0_baseline import main


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _default_commands() -> list[str]:
    return [
        'pip install -e ".[dev]"',
        'python -c "import orket"',
        "python -m orket.interfaces.orket_bundle_cli --help",
        'python -c "from orket.interfaces.api import create_api_app; create_api_app()"',
    ]


def test_record_phase0_baseline_writes_artifacts_and_sets_g1_green(tmp_path: Path) -> None:
    out_root = tmp_path / "td03052026"
    args = [
        "--out-root",
        str(out_root),
        "--phase-id",
        "phase0_baseline",
        "--install-mode",
        "editable_dev",
        "--canonical-source",
        "pyproject",
        "--import-smoke-status",
        "pass",
        "--entrypoint-help-status",
        "pass",
        "--api-app-construction-status",
        "pass",
        "--strict",
    ]
    for command in _default_commands():
        args.extend(["--command", command])

    exit_code = main(args)
    assert exit_code == 0

    commands_path = out_root / "phase0_baseline" / "commands.txt"
    env_path = out_root / "phase0_baseline" / "environment.json"
    result_path = out_root / "phase0_baseline" / "result.json"
    dashboard_path = out_root / "hardening_dashboard.json"

    assert commands_path.exists()
    assert env_path.exists()
    assert result_path.exists()
    assert dashboard_path.exists()

    assert commands_path.read_text(encoding="utf-8").startswith("1. ")
    environment_payload = _load_json(env_path)
    result_payload = _load_json(result_path)
    dashboard_payload = _load_json(dashboard_path)

    assert environment_payload["schema_version"] == "td03052026.environment.v1"
    assert "diff_ledger" in environment_payload
    assert result_payload["status"] == "PASS"
    assert "diff_ledger" in result_payload
    assert dashboard_payload["gates"]["G1"]["state"] == "green"
    assert "diff_ledger" in dashboard_payload


def test_record_phase0_baseline_strict_fails_when_required_smoke_fails(tmp_path: Path) -> None:
    out_root = tmp_path / "td03052026"
    args = [
        "--out-root",
        str(out_root),
        "--phase-id",
        "phase0_baseline",
        "--canonical-source",
        "pyproject",
        "--import-smoke-status",
        "fail",
        "--entrypoint-help-status",
        "pass",
        "--api-app-construction-status",
        "pass",
        "--strict",
    ]
    for command in _default_commands():
        args.extend(["--command", command])

    exit_code = main(args)
    assert exit_code == 1

    result_payload = _load_json(out_root / "phase0_baseline" / "result.json")
    dashboard_payload = _load_json(out_root / "hardening_dashboard.json")
    assert result_payload["status"] == "FAIL"
    assert dashboard_payload["gates"]["G1"]["state"] == "red"


def test_record_phase0_baseline_rejects_waived_for_p0_gate(tmp_path: Path) -> None:
    out_root = tmp_path / "td03052026"
    args = [
        "--out-root",
        str(out_root),
        "--phase-id",
        "phase0_baseline",
        "--canonical-source",
        "pyproject",
        "--import-smoke-status",
        "pass",
        "--entrypoint-help-status",
        "pass",
        "--api-app-construction-status",
        "pass",
        "--gate-state",
        "G1=waived:legacy",
    ]
    for command in _default_commands():
        args.extend(["--command", command])

    exit_code = main(args)
    assert exit_code == 2


def test_record_phase0_baseline_forces_g7_red_when_prerequisites_are_not_green(tmp_path: Path) -> None:
    out_root = tmp_path / "td03052026"
    args = [
        "--out-root",
        str(out_root),
        "--phase-id",
        "phase0_baseline",
        "--canonical-source",
        "pyproject",
        "--import-smoke-status",
        "pass",
        "--entrypoint-help-status",
        "pass",
        "--api-app-construction-status",
        "pass",
        "--gate-state",
        "G7=green:manual",
    ]
    for command in _default_commands():
        args.extend(["--command", command])

    exit_code = main(args)
    assert exit_code == 0

    dashboard_payload = _load_json(out_root / "hardening_dashboard.json")
    assert dashboard_payload["gates"]["G7"]["state"] == "red"
    assert "cannot be green" in dashboard_payload["gates"]["G7"]["detail"]

