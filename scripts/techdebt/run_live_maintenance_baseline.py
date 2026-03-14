from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping
from zoneinfo import ZoneInfo

import aiofiles

try:
    from scripts.common.evidence_environment import DEFAULT_EVIDENCE_ENV_KEYS
    from scripts.common.evidence_environment import collect_environment_metadata
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.evidence_environment import DEFAULT_EVIDENCE_ENV_KEYS
    from common.evidence_environment import collect_environment_metadata
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


LOCAL_TIMEZONE = ZoneInfo("America/Denver")
DEFAULT_BASELINE_ROOT = Path("benchmarks/results/techdebt/live_maintenance_baseline")
DEFAULT_PYTEST_NODE = "tests/acceptance/test_sandbox_orchestrator_live_docker.py::test_live_create_health_and_cleanup_flow"
DEFAULT_PACKAGE_MODE = "editable_dev"
DEFAULT_TIMEOUT_SECONDS = 1800
PYTEST_ENV_OVERRIDES = {"ORKET_RUN_SANDBOX_ACCEPTANCE": "1"}


@dataclass(frozen=True)
class CommandSpec:
    result_key: str
    display: str
    argv: tuple[str, ...]
    timeout_seconds: int
    env_overrides: Mapping[str, str] | None = None


@dataclass(frozen=True)
class CommandOutcome:
    result_key: str
    command: str
    returncode: int
    status: str
    detail: str
    duration_seconds: float
    stdout: str
    stderr: str


Runner = Callable[[CommandSpec, Path], Awaitable[CommandOutcome]]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the canonical live maintenance baseline and record evidence.",
    )
    parser.add_argument(
        "--baseline-id",
        required=True,
        help="Stable baseline identifier, e.g. 2026-03-14_sandbox-baseline.",
    )
    parser.add_argument(
        "--baseline-root-base",
        default=str(DEFAULT_BASELINE_ROOT),
        help="Base directory for live maintenance baseline artifacts.",
    )
    parser.add_argument(
        "--pytest-node",
        default=DEFAULT_PYTEST_NODE,
        help="Pytest node id for the canonical live baseline target.",
    )
    parser.add_argument(
        "--package-mode",
        default=DEFAULT_PACKAGE_MODE,
        help="Package/install mode label for environment metadata.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout for the live pytest command.",
    )
    parser.add_argument("--env-key", action="append", default=[], help="Additional env keys to capture.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless the live baseline succeeds.")
    return parser


def _local_date_str() -> str:
    return datetime.now(LOCAL_TIMEZONE).date().isoformat()


def _validate_baseline_id(baseline_id: str) -> str:
    clean = str(baseline_id or "").strip()
    if not clean:
        raise ValueError("baseline-id must not be empty")
    if any(token in clean for token in ("/", "\\", ":")):
        raise ValueError(f"baseline-id contains unsupported path characters: {clean}")
    return clean


def _display_pytest_command(*, basetemp: Path, pytest_node: str) -> str:
    return (
        "ORKET_RUN_SANDBOX_ACCEPTANCE=1 "
        f"{sys.executable} -m pytest -q -s --basetemp {basetemp.as_posix()} {pytest_node}"
    )


def _command_specs(*, basetemp: Path, pytest_node: str, timeout_seconds: int) -> list[CommandSpec]:
    python = sys.executable
    return [
        CommandSpec(
            result_key="docker_info",
            display="docker info --format {{json .}}",
            argv=("docker", "info", "--format", "{{json .}}"),
            timeout_seconds=60,
        ),
        CommandSpec(
            result_key="docker_compose_version",
            display="docker-compose version --short",
            argv=("docker-compose", "version", "--short"),
            timeout_seconds=60,
        ),
        CommandSpec(
            result_key="baseline_pytest",
            display=_display_pytest_command(basetemp=basetemp, pytest_node=pytest_node),
            argv=(python, "-m", "pytest", "-q", "-s", "--basetemp", str(basetemp), pytest_node),
            timeout_seconds=max(60, int(timeout_seconds)),
            env_overrides=PYTEST_ENV_OVERRIDES,
        ),
    ]


async def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8", newline="\n") as handle:
        await handle.write(content)


def _last_nonempty_line(text: str) -> str:
    for line in reversed(str(text or "").splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _extract_pytest_summary(text: str) -> str:
    for line in reversed(str(text or "").splitlines()):
        token = line.strip()
        if token and (" passed" in token or " failed" in token or " skipped" in token):
            return token
    return _last_nonempty_line(text)


def _pytest_skipped(summary: str) -> bool:
    lowered = str(summary or "").lower()
    return " skipped" in lowered and " passed" not in lowered and " failed" not in lowered


def _render_log(outcomes: list[CommandOutcome], *, stream_name: str) -> str:
    blocks: list[str] = []
    for outcome in outcomes:
        payload = outcome.stdout if stream_name == "stdout" else outcome.stderr
        blocks.append(f"## {outcome.result_key} | {outcome.command}\n{payload.rstrip() or '<empty>'}\n")
    return "\n".join(blocks).rstrip() + "\n"


def _command_detail(*, result_key: str, stdout: str, stderr: str, returncode: int) -> str:
    if result_key == "baseline_pytest":
        return _extract_pytest_summary(stdout)
    if result_key == "docker_info":
        try:
            payload = json.loads(_last_nonempty_line(stdout))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            version = str(payload.get("ServerVersion") or "").strip() or "unknown"
            name = str(payload.get("Name") or "").strip() or "unknown"
            return f"ServerVersion={version}; Name={name}"
    return _last_nonempty_line(stdout) or _last_nonempty_line(stderr) or f"returncode={returncode}"


async def _default_runner(spec: CommandSpec, cwd: Path) -> CommandOutcome:
    started = time.perf_counter()
    env = dict(os.environ)
    if spec.env_overrides:
        env.update({str(key): str(value) for key, value in spec.env_overrides.items()})
    try:
        process = await asyncio.create_subprocess_exec(
            *spec.argv,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        duration = round(time.perf_counter() - started, 3)
        detail = f"command not found: {spec.argv[0]}"
        return CommandOutcome(
            result_key=spec.result_key,
            command=spec.display,
            returncode=127,
            status="FAIL",
            detail=detail,
            duration_seconds=duration,
            stdout="",
            stderr=detail,
        )

    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(process.communicate(), timeout=spec.timeout_seconds)
    except asyncio.TimeoutError:
        process.kill()
        stdout_raw, stderr_raw = await process.communicate()
        duration = round(time.perf_counter() - started, 3)
        detail = f"timed out after {spec.timeout_seconds}s"
        return CommandOutcome(
            result_key=spec.result_key,
            command=spec.display,
            returncode=124,
            status="FAIL",
            detail=detail,
            duration_seconds=duration,
            stdout=(stdout_raw or b"").decode("utf-8", errors="replace"),
            stderr=((stderr_raw or b"").decode("utf-8", errors="replace") or detail),
        )

    duration = round(time.perf_counter() - started, 3)
    stdout = (stdout_raw or b"").decode("utf-8", errors="replace")
    stderr = (stderr_raw or b"").decode("utf-8", errors="replace")
    status = "PASS" if process.returncode == 0 else "FAIL"
    detail = _command_detail(
        result_key=spec.result_key,
        stdout=stdout,
        stderr=stderr,
        returncode=int(process.returncode or 0),
    )
    return CommandOutcome(
        result_key=spec.result_key,
        command=spec.display,
        returncode=int(process.returncode or 0),
        status=status,
        detail=detail or f"returncode={int(process.returncode or 0)}",
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr,
    )


def _not_run_outcome(spec: CommandSpec, *, reason: str) -> CommandOutcome:
    return CommandOutcome(
        result_key=spec.result_key,
        command=spec.display,
        returncode=-1,
        status="NOT_RUN",
        detail=reason,
        duration_seconds=0.0,
        stdout="",
        stderr="",
    )


def _serialize_outcome(outcome: CommandOutcome) -> dict[str, Any]:
    return {
        "id": outcome.result_key,
        "command": outcome.command,
        "returncode": outcome.returncode,
        "status": outcome.status,
        "detail": outcome.detail,
        "duration_seconds": outcome.duration_seconds,
    }


def _results_summary(outcomes: list[CommandOutcome]) -> dict[str, str]:
    summary: dict[str, str] = {}
    for outcome in outcomes:
        label = outcome.status
        if outcome.status == "FAIL":
            label = f"FAIL ({outcome.detail})"
        elif outcome.status == "NOT_RUN":
            label = f"NOT_RUN ({outcome.detail})"
        elif outcome.result_key == "baseline_pytest" and outcome.detail:
            label = f"PASS ({outcome.detail})"
        summary[outcome.result_key] = label
    return summary


def _classify_result(outcomes: list[CommandOutcome]) -> tuple[str, str, list[str]]:
    by_key = {outcome.result_key: outcome for outcome in outcomes}
    docker_info = by_key["docker_info"]
    docker_compose = by_key["docker_compose_version"]
    pytest_outcome = by_key["baseline_pytest"]

    notes: list[str] = []
    if docker_info.status != "PASS" or docker_compose.status != "PASS":
        if docker_info.status != "PASS":
            notes.append(f"docker preflight failed: {docker_info.detail}")
        if docker_compose.status != "PASS":
            notes.append(f"docker-compose preflight failed: {docker_compose.detail}")
        return "blocked", "environment blocker", notes

    if pytest_outcome.status == "NOT_RUN":
        notes.append(f"baseline pytest did not run: {pytest_outcome.detail}")
        return "blocked", "environment blocker", notes

    if pytest_outcome.status == "PASS":
        if _pytest_skipped(pytest_outcome.detail):
            notes.append(f"baseline pytest skipped: {pytest_outcome.detail}")
            return "blocked", "environment blocker", notes
        notes.append(f"baseline pytest passed: {pytest_outcome.detail}")
        return "primary", "success", notes

    notes.append(f"baseline pytest failed: {pytest_outcome.detail}")
    return "primary", "failure", notes


def _build_assertions(*, outcomes: list[CommandOutcome], path: str, result: str) -> list[dict[str, Any]]:
    by_key = {outcome.result_key: outcome for outcome in outcomes}
    pytest_outcome = by_key["baseline_pytest"]
    return [
        {
            "id": "docker_info_passed",
            "passed": by_key["docker_info"].status == "PASS",
            "detail": f"status={by_key['docker_info'].status}; detail={by_key['docker_info'].detail}",
        },
        {
            "id": "docker_compose_version_passed",
            "passed": by_key["docker_compose_version"].status == "PASS",
            "detail": f"status={by_key['docker_compose_version'].status}; detail={by_key['docker_compose_version'].detail}",
        },
        {
            "id": "baseline_pytest_passed",
            "passed": pytest_outcome.status == "PASS" and not _pytest_skipped(pytest_outcome.detail),
            "detail": f"status={pytest_outcome.status}; detail={pytest_outcome.detail}",
        },
        {
            "id": "live_path_recorded",
            "passed": path in {"primary", "blocked"},
            "detail": f"path={path}; result={result}",
        },
    ]


def _build_result_payload(
    *,
    baseline_id: str,
    baseline_root: Path,
    environment_path: Path,
    commands_path: Path,
    stdout_log: Path,
    stderr_log: Path,
    pytest_node: str,
    pytest_basetemp: Path,
    outcomes: list[CommandOutcome],
) -> dict[str, Any]:
    path, result, notes = _classify_result(outcomes)
    assertions = _build_assertions(outcomes=outcomes, path=path, result=result)
    status = "pass" if result == "success" else ("blocked" if result == "environment blocker" else "fail")
    return {
        "schema_version": "techdebt.live_maintenance_baseline.v1",
        "baseline_id": baseline_id,
        "generated_on": _local_date_str(),
        "proof_type": "live",
        "status": status,
        "path": path,
        "result": result,
        "baseline_target": {
            "pytest_node": pytest_node,
            "pytest_basetemp": pytest_basetemp.as_posix(),
        },
        "evidence": {
            "baseline_root": baseline_root.as_posix(),
            "commands_path": commands_path.as_posix(),
            "environment": environment_path.as_posix(),
            "stdout_log": stdout_log.as_posix(),
            "stderr_log": stderr_log.as_posix(),
            "results": _results_summary(outcomes),
        },
        "command_results": [_serialize_outcome(outcome) for outcome in outcomes],
        "assertions": assertions,
        "notes": notes,
    }


async def run_baseline(argv: list[str] | None = None, *, runner: Runner = _default_runner) -> int:
    args = _build_parser().parse_args(argv)
    baseline_id = _validate_baseline_id(str(args.baseline_id))
    baseline_root = Path(str(args.baseline_root_base)) / baseline_id
    pytest_basetemp = baseline_root / "pytest_tmp"
    commands_path = baseline_root / "commands.txt"
    environment_path = baseline_root / "environment.json"
    stdout_log = baseline_root / "stdout.log"
    stderr_log = baseline_root / "stderr.log"
    result_path = baseline_root / "result.json"

    specs = _command_specs(
        basetemp=pytest_basetemp,
        pytest_node=str(args.pytest_node),
        timeout_seconds=int(args.timeout_seconds),
    )
    await _write_text(
        commands_path,
        "\n".join(f"{index}. {spec.display}" for index, spec in enumerate(specs, start=1)) + "\n",
    )

    env_keys = sorted(
        set(DEFAULT_EVIDENCE_ENV_KEYS)
        | {"ORKET_RUN_SANDBOX_ACCEPTANCE"}
        | {str(item).strip() for item in list(args.env_key or []) if str(item).strip()}
    )
    environment_payload = collect_environment_metadata(
        schema_version="techdebt.live_maintenance_baseline.environment.v1",
        package_mode=str(args.package_mode),
        env_keys=env_keys,
        extra_fields={
            "baseline_id": baseline_id,
            "generated_on": _local_date_str(),
            "pytest_node": str(args.pytest_node),
            "command_env_overrides": dict(PYTEST_ENV_OVERRIDES),
        },
    )
    environment_payload.setdefault("env_toggles", {})
    environment_payload["env_toggles"]["ORKET_RUN_SANDBOX_ACCEPTANCE"] = {"set": True, "value": "1"}
    write_payload_with_diff_ledger(environment_path, environment_payload)

    repo_root = Path.cwd()
    outcomes: list[CommandOutcome] = []
    for spec in specs[:2]:
        outcomes.append(await runner(spec, repo_root))
    if all(outcome.status == "PASS" for outcome in outcomes):
        outcomes.append(await runner(specs[2], repo_root))
    else:
        outcomes.append(_not_run_outcome(specs[2], reason="blocked by docker preflight failure"))

    await _write_text(stdout_log, _render_log(outcomes, stream_name="stdout"))
    await _write_text(stderr_log, _render_log(outcomes, stream_name="stderr"))

    result_payload = _build_result_payload(
        baseline_id=baseline_id,
        baseline_root=baseline_root,
        environment_path=environment_path,
        commands_path=commands_path,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
        pytest_node=str(args.pytest_node),
        pytest_basetemp=pytest_basetemp,
        outcomes=outcomes,
    )
    write_payload_with_diff_ledger(result_path, result_payload)

    if bool(args.strict) and result_payload["result"] != "success":
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(run_baseline(argv))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
