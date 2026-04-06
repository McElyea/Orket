# LIFECYCLE: live
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from scripts.techdebt.run_live_maintenance_baseline import CommandOutcome, CommandSpec, main, run_baseline


def _load_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def _runner_factory(*, docker_fail: bool = False, pytest_summary: str = "1 passed in 0.50s") -> callable:
    async def _runner(spec: CommandSpec, _cwd: Path) -> CommandOutcome:
        if spec.result_key == "docker_info":
            return CommandOutcome(
                result_key=spec.result_key,
                command=spec.display,
                returncode=1 if docker_fail else 0,
                status="FAIL" if docker_fail else "PASS",
                detail="docker daemon unavailable" if docker_fail else "ServerVersion=27.0.0",
                duration_seconds=0.01,
                stdout="" if docker_fail else '{"ServerVersion":"27.0.0"}\n',
                stderr="daemon unavailable" if docker_fail else "",
            )
        if spec.result_key == "docker_compose_version":
            return CommandOutcome(
                result_key=spec.result_key,
                command=spec.display,
                returncode=0,
                status="PASS",
                detail="2.29.0",
                duration_seconds=0.01,
                stdout="2.29.0\n",
                stderr="",
            )
        return CommandOutcome(
            result_key=spec.result_key,
            command=spec.display,
            returncode=0,
            status="PASS",
            detail=pytest_summary,
            duration_seconds=0.2,
            stdout=f"{pytest_summary}\n",
            stderr="",
        )

    return _runner


# Layer: contract
def test_run_live_maintenance_baseline_writes_green_evidence(tmp_path: Path) -> None:
    exit_code = asyncio.run(
        run_baseline(
            [
                "--baseline-id",
                "2026-03-14_sandbox-baseline",
                "--baseline-root-base",
                str(tmp_path / "live-baseline"),
                "--strict",
            ],
            runner=_runner_factory(),
        )
    )

    baseline_root = tmp_path / "live-baseline" / "2026-03-14_sandbox-baseline"
    result_payload = _load_json(baseline_root / "result.json")
    environment_payload = _load_json(baseline_root / "environment.json")

    assert exit_code == 0
    assert (baseline_root / "commands.txt").exists()
    assert (baseline_root / "stdout.log").exists()
    assert (baseline_root / "stderr.log").exists()
    assert result_payload["result"] == "success"
    assert result_payload["path"] == "primary"
    assert result_payload["evidence"]["results"]["baseline_pytest"] == "PASS (1 passed in 0.50s)"
    assert environment_payload["command_env_overrides"]["ORKET_RUN_SANDBOX_ACCEPTANCE"] == "1"
    assert "diff_ledger" in result_payload
    assert "diff_ledger" in environment_payload


# Layer: contract
def test_run_live_maintenance_baseline_marks_environment_blocker_when_docker_preflight_fails(tmp_path: Path) -> None:
    exit_code = asyncio.run(
        run_baseline(
            [
                "--baseline-id",
                "2026-03-14_sandbox-baseline",
                "--baseline-root-base",
                str(tmp_path / "live-baseline"),
                "--strict",
            ],
            runner=_runner_factory(docker_fail=True),
        )
    )

    result_payload = _load_json(tmp_path / "live-baseline" / "2026-03-14_sandbox-baseline" / "result.json")

    assert exit_code == 1
    assert result_payload["status"] == "blocked"
    assert result_payload["result"] == "environment blocker"
    assert result_payload["evidence"]["results"]["baseline_pytest"].startswith("NOT_RUN")


# Layer: contract
def test_run_live_maintenance_baseline_marks_skip_as_environment_blocker(tmp_path: Path) -> None:
    exit_code = asyncio.run(
        run_baseline(
            [
                "--baseline-id",
                "2026-03-14_sandbox-baseline",
                "--baseline-root-base",
                str(tmp_path / "live-baseline"),
                "--strict",
            ],
            runner=_runner_factory(pytest_summary="1 skipped in 0.50s"),
        )
    )

    result_payload = _load_json(tmp_path / "live-baseline" / "2026-03-14_sandbox-baseline" / "result.json")

    assert exit_code == 1
    assert result_payload["status"] == "blocked"
    assert result_payload["result"] == "environment blocker"


# Layer: unit
def test_run_live_maintenance_baseline_rejects_invalid_baseline_id() -> None:
    exit_code = main(["--baseline-id", "bad/name"])
    assert exit_code == 2
