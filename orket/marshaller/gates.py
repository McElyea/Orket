from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process import ProcessResult, run_process
from .rejection_codes import BUILD_FAILED, FLAKE_DETECTED, LINT_FAILED, POLICY_DENY, TESTS_FAILED


@dataclass(frozen=True)
class GateResult:
    name: str
    command: tuple[str, ...]
    attempts: tuple[ProcessResult, ...]
    passed: bool
    flake_detected: bool
    rejection_code: str | None

    @property
    def log_text(self) -> str:
        lines: list[str] = []
        for idx, attempt in enumerate(self.attempts, start=1):
            lines.append(f"[attempt {idx}] returncode={attempt.returncode} timed_out={attempt.timed_out}")
            if attempt.stdout:
                lines.append("stdout:")
                lines.append(attempt.stdout.rstrip("\n"))
            if attempt.stderr:
                lines.append("stderr:")
                lines.append(attempt.stderr.rstrip("\n"))
        return "\n".join(lines).rstrip() + "\n"

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": list(self.command),
            "passed": self.passed,
            "flake_detected": self.flake_detected,
            "rejection_code": self.rejection_code,
            "attempts": [
                {
                    "returncode": row.returncode,
                    "timed_out": row.timed_out,
                }
                for row in self.attempts
            ],
        }


async def run_gate(
    *,
    name: str,
    command: Sequence[str],
    cwd: Path,
    env: dict[str, str],
    flake_mode: str,
    max_retries: int,
    timeout_seconds: float | None,
) -> GateResult:
    attempts: list[ProcessResult] = []
    first = await run_process(command, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
    attempts.append(first)
    if first.returncode == 0:
        return GateResult(
            name=name,
            command=tuple(command),
            attempts=tuple(attempts),
            passed=True,
            flake_detected=False,
            rejection_code=None,
        )

    retries = max(0, int(max_retries)) if flake_mode in {"retry_then_deny", "quarantine_allow"} else 0
    for _ in range(retries):
        attempts.append(await run_process(command, cwd=cwd, env=env, timeout_seconds=timeout_seconds))

    outcomes = {row.returncode == 0 for row in attempts}
    flake_detected = len(outcomes) > 1
    if flake_detected and flake_mode == "quarantine_allow":
        return GateResult(
            name=name,
            command=tuple(command),
            attempts=tuple(attempts),
            passed=True,
            flake_detected=True,
            rejection_code=None,
        )
    if flake_detected:
        return GateResult(
            name=name,
            command=tuple(command),
            attempts=tuple(attempts),
            passed=False,
            flake_detected=True,
            rejection_code=FLAKE_DETECTED,
        )
    return GateResult(
        name=name,
        command=tuple(command),
        attempts=tuple(attempts),
        passed=False,
        flake_detected=False,
        rejection_code=_rejection_for_gate(name),
    )


def resolve_gate_command(task_spec: dict[str, Any], check_name: str) -> tuple[str, ...]:
    commands = task_spec.get("gate_commands")
    if not isinstance(commands, dict):
        return ()
    value = commands.get(check_name)
    if not isinstance(value, list):
        return ()
    parts = [str(item).strip() for item in value if str(item).strip()]
    return tuple(parts)


def _rejection_for_gate(name: str) -> str:
    normalized = str(name).strip().lower()
    if normalized == "build":
        return BUILD_FAILED
    if normalized == "test":
        return TESTS_FAILED
    if normalized == "lint":
        return LINT_FAILED
    return POLICY_DENY
