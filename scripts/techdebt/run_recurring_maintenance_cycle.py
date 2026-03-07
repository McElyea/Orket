from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

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
DEFAULT_CYCLE_ROOT = Path("benchmarks/results/techdebt/recurring")
DEFAULT_REPORT_ROOT = Path("tests/reports")
DEFAULT_READINESS_OUT = Path("benchmarks/results/techdebt/td03052026/readiness_checklist.json")
DEFAULT_SECTION_B_SKIP_REASON = "not a release-candidate or enforce-window refresh cycle"
DEFAULT_SECTION_C_SKIP_REASON = "no provider/model/template-local-prompting promotion campaign in this cycle"
DEFAULT_SECTION_D_NOTE = "No recurring checklist curation changes were required in this cycle."


@dataclass(frozen=True)
class CommandSpec:
    result_key: str
    display: str
    argv: tuple[str, ...]
    timeout_seconds: int


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


Runner = Callable[[Sequence[str], Path, int], subprocess.CompletedProcess[str]]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the recurring techdebt maintenance cycle and record evidence.")
    parser.add_argument("--cycle-id", required=True, help="Stable cycle identifier, e.g. 2026-03-07_cycle-a.")
    parser.add_argument("--cycle-root-base", default=str(DEFAULT_CYCLE_ROOT), help="Base directory for cycle artifacts.")
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT), help="Directory for summarized cycle reports.")
    parser.add_argument("--readiness-out", default=str(DEFAULT_READINESS_OUT), help="TD03052026 readiness artifact path.")
    parser.add_argument("--package-mode", default="editable_dev", help="Package/install mode label for evidence metadata.")
    parser.add_argument("--env-key", action="append", default=[], help="Additional env keys to capture.")
    parser.add_argument(
        "--section-b-skip-reason",
        default=DEFAULT_SECTION_B_SKIP_REASON,
        help="Reason recorded when conditional Section B is not executed.",
    )
    parser.add_argument(
        "--section-c-skip-reason",
        default=DEFAULT_SECTION_C_SKIP_REASON,
        help="Reason recorded when conditional Section C is not executed.",
    )
    parser.add_argument(
        "--section-d-note",
        default=DEFAULT_SECTION_D_NOTE,
        help="Operator note recorded for required Section D curation review.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when required maintenance sections are not green.")
    return parser


def _default_runner(argv: Sequence[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )


def _local_date_str() -> str:
    return datetime.now(LOCAL_TIMEZONE).date().isoformat()


def _validate_cycle_id(cycle_id: str) -> str:
    clean = str(cycle_id or "").strip()
    if not clean:
        raise ValueError("cycle-id must not be empty")
    if any(token in clean for token in ("/", "\\", ":")):
        raise ValueError(f"cycle-id contains unsupported path characters: {clean}")
    return clean


def _report_file_name(cycle_id: str) -> str:
    if "_cycle-" in cycle_id:
        prefix, suffix = cycle_id.split("_cycle-", 1)
        if prefix and suffix:
            return f"techdebt_recurring_cycle_{prefix}_{suffix}_report.json"
    normalized = cycle_id.replace("-", "_")
    return f"techdebt_recurring_cycle_{normalized}_report.json"


def _command_specs(readiness_out: Path) -> list[CommandSpec]:
    python = sys.executable
    return [
        CommandSpec(
            result_key="td03052026_gate_audit",
            display=(
                "python scripts/governance/check_td03052026_gate_audit.py "
                f"--require-ready --out {readiness_out.as_posix()}"
            ),
            argv=(python, "scripts/governance/check_td03052026_gate_audit.py", "--require-ready", "--out", str(readiness_out)),
            timeout_seconds=120,
        ),
        CommandSpec(
            result_key="docs_project_hygiene",
            display="python scripts/governance/check_docs_project_hygiene.py",
            argv=(python, "scripts/governance/check_docs_project_hygiene.py"),
            timeout_seconds=120,
        ),
        CommandSpec(
            result_key="pytest",
            display="python -m pytest -q",
            argv=(python, "-m", "pytest", "-q"),
            timeout_seconds=1800,
        ),
    ]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_log(outcomes: list[CommandOutcome], *, stream_name: str) -> str:
    blocks: list[str] = []
    for outcome in outcomes:
        payload = outcome.stdout if stream_name == "stdout" else outcome.stderr
        blocks.append(f"## {outcome.result_key} | {outcome.command}\n{payload.rstrip() or '<empty>'}\n")
    return "\n".join(blocks).rstrip() + "\n"


def _last_nonempty_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _execute_command(spec: CommandSpec, cwd: Path, runner: Runner) -> CommandOutcome:
    started = time.perf_counter()
    try:
        completed = runner(spec.argv, cwd, spec.timeout_seconds)
        duration = round(time.perf_counter() - started, 3)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        status = "PASS" if completed.returncode == 0 else "FAIL"
        detail = _last_nonempty_line(stdout) or _last_nonempty_line(stderr) or f"returncode={completed.returncode}"
        return CommandOutcome(
            result_key=spec.result_key,
            command=spec.display,
            returncode=int(completed.returncode),
            status=status,
            detail=detail,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.perf_counter() - started, 3)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        detail = f"timed out after {spec.timeout_seconds}s"
        return CommandOutcome(
            result_key=spec.result_key,
            command=spec.display,
            returncode=124,
            status="FAIL",
            detail=detail,
            duration_seconds=duration,
            stdout=stdout,
            stderr=stderr or detail,
        )


def _results_summary(outcomes: list[CommandOutcome]) -> dict[str, str]:
    summary: dict[str, str] = {}
    for outcome in outcomes:
        label = outcome.status
        if outcome.result_key == "pytest":
            pytest_tail = _last_nonempty_line(outcome.stdout)
            if pytest_tail and outcome.status == "PASS":
                label = f"PASS ({pytest_tail})"
            elif pytest_tail:
                label = f"FAIL ({pytest_tail})"
        elif outcome.status == "FAIL":
            label = f"FAIL ({outcome.detail})"
        summary[outcome.result_key] = label
    return summary


def _assertions(outcomes: list[CommandOutcome], section_d_note: str) -> list[dict[str, Any]]:
    checks = {
        "section_a_td03052026_gate_audit_passed": "td03052026_gate_audit",
        "section_a_docs_project_hygiene_passed": "docs_project_hygiene",
        "section_a_canonical_pytest_passed": "pytest",
    }
    by_key = {outcome.result_key: outcome for outcome in outcomes}
    assertions: list[dict[str, Any]] = []
    for assertion_id, result_key in checks.items():
        outcome = by_key[result_key]
        assertions.append(
            {
                "id": assertion_id,
                "passed": outcome.status == "PASS",
                "detail": f"status={outcome.status}; detail={outcome.detail}",
            }
        )
    assertions.append(
        {
            "id": "section_d_review_note_recorded",
            "passed": bool(str(section_d_note or "").strip()),
            "detail": str(section_d_note or "").strip() or "<missing>",
        }
    )
    return assertions


def _build_payload(
    *,
    cycle_id: str,
    cycle_root: Path,
    readiness_out: Path,
    report_out: Path,
    stdout_log: Path,
    stderr_log: Path,
    environment_path: Path,
    outcomes: list[CommandOutcome],
    section_b_skip_reason: str,
    section_c_skip_reason: str,
    section_d_note: str,
) -> dict[str, Any]:
    assertions = _assertions(outcomes, section_d_note)
    section_a_passed = all(outcome.status == "PASS" for outcome in outcomes)
    section_d_passed = bool(str(section_d_note or "").strip())
    status = "pass" if section_a_passed and section_d_passed else "fail"
    command_results = [
        {
            "id": outcome.result_key,
            "command": outcome.command,
            "returncode": outcome.returncode,
            "status": outcome.status,
            "detail": outcome.detail,
            "duration_seconds": outcome.duration_seconds,
        }
        for outcome in outcomes
    ]
    notes = [
        "Section A remains green (G1-G7)." if section_a_passed else "Section A reported one or more failing checks.",
        str(section_d_note).strip(),
    ]
    return {
        "schema_version": "techdebt.recurring_cycle.v1",
        "cycle_id": cycle_id,
        "status": status,
        "generated_on": _local_date_str(),
        "sections_executed": ["A", "D"],
        "sections_skipped": [
            {"section": "B", "reason": str(section_b_skip_reason).strip()},
            {"section": "C", "reason": str(section_c_skip_reason).strip()},
        ],
        "evidence": {
            "commands": [outcome.command for outcome in outcomes],
            "results": _results_summary(outcomes),
            "cycle_root": cycle_root.as_posix(),
            "tracked_artifact": readiness_out.as_posix(),
            "stdout_log": stdout_log.as_posix(),
            "stderr_log": stderr_log.as_posix(),
            "environment": environment_path.as_posix(),
            "report": report_out.as_posix(),
        },
        "sections": {
            "A": {
                "status": "PASS" if section_a_passed else "FAIL",
                "command_results": command_results,
            },
            "B": {"status": "SKIPPED", "reason": str(section_b_skip_reason).strip()},
            "C": {"status": "SKIPPED", "reason": str(section_c_skip_reason).strip()},
            "D": {"status": "PASS" if section_d_passed else "FAIL", "note": str(section_d_note).strip()},
        },
        "assertions": assertions,
        "notes": notes,
    }


def run_cycle(argv: list[str] | None = None, *, runner: Runner = _default_runner) -> int:
    args = _build_parser().parse_args(argv)
    cycle_id = _validate_cycle_id(str(args.cycle_id))
    cycle_root = Path(str(args.cycle_root_base)) / cycle_id
    report_out = Path(str(args.report_root)) / _report_file_name(cycle_id)
    readiness_out = Path(str(args.readiness_out))
    commands_path = cycle_root / "commands.txt"
    environment_path = cycle_root / "environment.json"
    stdout_log = cycle_root / "stdout.log"
    stderr_log = cycle_root / "stderr.log"
    result_path = cycle_root / "result.json"

    specs = _command_specs(readiness_out)
    _write_text(commands_path, "\n".join(f"{index}. {spec.display}" for index, spec in enumerate(specs, start=1)) + "\n")

    env_keys = sorted(set(DEFAULT_EVIDENCE_ENV_KEYS) | {str(item).strip() for item in list(args.env_key or []) if str(item).strip()})
    environment_payload = collect_environment_metadata(
        schema_version="techdebt.recurring.environment.v1",
        package_mode=str(args.package_mode),
        env_keys=env_keys,
        extra_fields={
            "cycle_id": cycle_id,
            "generated_on": _local_date_str(),
        },
    )
    write_payload_with_diff_ledger(environment_path, environment_payload)

    repo_root = Path.cwd()
    outcomes = [_execute_command(spec, repo_root, runner) for spec in specs]
    _write_text(stdout_log, _render_log(outcomes, stream_name="stdout"))
    _write_text(stderr_log, _render_log(outcomes, stream_name="stderr"))

    payload = _build_payload(
        cycle_id=cycle_id,
        cycle_root=cycle_root,
        readiness_out=readiness_out,
        report_out=report_out,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
        environment_path=environment_path,
        outcomes=outcomes,
        section_b_skip_reason=str(args.section_b_skip_reason),
        section_c_skip_reason=str(args.section_c_skip_reason),
        section_d_note=str(args.section_d_note),
    )
    write_payload_with_diff_ledger(result_path, payload)
    write_payload_with_diff_ledger(report_out, payload)

    required_green = payload["status"] == "pass"
    if bool(args.strict) and not required_green:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run_cycle(argv)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
