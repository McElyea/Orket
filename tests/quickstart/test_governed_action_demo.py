from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from orket.quickstart.governed_action_demo import (
    OUTPUT_CONTENT,
    OUTPUT_RELATIVE_PATH,
    main,
    run_governed_action_demo,
)
from orket.quickstart.ledger import load_ledger_events, verify_ledger_events

APPROVED_EVENTS = [
    "run_started",
    "tool_call_proposed",
    "approval_requested",
    "operator_approved",
    "tool_effect_executed",
    "run_finished",
]
DENIED_EVENTS = [
    "run_started",
    "tool_call_proposed",
    "approval_requested",
    "operator_denied",
    "tool_effect_skipped",
    "run_finished",
]
INVALID_EVENTS = [
    "run_started",
    "tool_call_proposed",
    "approval_requested",
    "operator_input_invalid",
    "tool_effect_skipped",
    "run_finished",
]


def _timestamp_factory():
    counter = 0

    def _next() -> str:
        nonlocal counter
        counter += 1
        return f"2026-05-25T00:01:{counter:02d}Z"

    return _next


async def _run_demo(tmp_path: Path, operator_input: str, run_id: str):
    lines: list[str] = []
    prompts: list[str] = []

    def _input(prompt: str) -> str:
        prompts.append(prompt)
        return operator_input

    result = await run_governed_action_demo(
        workspace=tmp_path,
        input_func=_input,
        output_func=lines.append,
        run_id_factory=lambda: run_id,
        timestamp_factory=_timestamp_factory(),
    )
    events = await load_ledger_events(result.ledger_path)
    return result, events, lines, prompts


# Layer: integration
@pytest.mark.integration
@pytest.mark.asyncio
async def test_approval_executes_file_and_emits_required_ledger(tmp_path: Path) -> None:
    """Layer: integration. Proves approval writes the file only after operator approval and emits the chain."""
    result, events, lines, prompts = await _run_demo(tmp_path, "approve", "run-approved")

    output_path = tmp_path / OUTPUT_RELATIVE_PATH
    verify_result = verify_ledger_events(events)

    assert result.terminal_status == "approved_executed"
    assert result.action_executed is True
    assert result.output_path == output_path
    assert output_path.read_text(encoding="utf-8") == OUTPUT_CONTENT
    assert [event["event_type"] for event in events] == APPROVED_EVENTS
    assert events[-1]["payload"]["terminal_status"] == "approved_executed"
    assert verify_result.valid is True
    assert "GOVERNED ACTION REQUEST" in lines
    assert "tool: write_file" in lines
    assert "path: quickstart_out/hello_from_orket.txt" in lines
    assert prompts == ["Approve this action? [a]pprove / [d]eny: "]
    assert result.verifier_command == (
        "python -m orket.quickstart.verify_ledger .orket/quickstart/runs/run-approved/ledger.jsonl"
    )


# Layer: integration
@pytest.mark.integration
@pytest.mark.asyncio
async def test_denial_skips_file_and_records_denial_reason(tmp_path: Path) -> None:
    """Layer: integration. Proves denial leaves the proposed file absent and records a skipped effect."""
    result, events, _lines, _prompts = await _run_demo(tmp_path, "deny", "run-denied")

    assert result.terminal_status == "denied_skipped"
    assert result.action_executed is False
    assert result.output_path is None
    assert (tmp_path / OUTPUT_RELATIVE_PATH).exists() is False
    assert [event["event_type"] for event in events] == DENIED_EVENTS
    assert events[4]["payload"]["reason"] == "operator_denied"
    assert events[-1]["payload"]["terminal_status"] == "denied_skipped"
    assert verify_ledger_events(events).valid is True


# Layer: integration
@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_input_fails_closed_and_records_invalid_input(tmp_path: Path) -> None:
    """Layer: integration. Proves unexpected operator input skips the write and remains ledger-verifiable."""
    result, events, _lines, _prompts = await _run_demo(tmp_path, "later", "run-invalid")

    assert result.terminal_status == "invalid_input_skipped"
    assert result.action_executed is False
    assert result.output_path is None
    assert (tmp_path / OUTPUT_RELATIVE_PATH).exists() is False
    assert [event["event_type"] for event in events] == INVALID_EVENTS
    assert events[3]["payload"]["operator_input"] == "later"
    assert events[4]["payload"]["reason"] == "invalid_operator_input"
    assert events[-1]["payload"]["terminal_status"] == "invalid_input_skipped"
    assert verify_ledger_events(events).valid is True


# Layer: live_truth
@pytest.mark.end_to_end
def test_cli_scripted_denial_is_noninteractive_and_successful(tmp_path: Path) -> None:
    """Layer: end-to-end. Proves the quickstart supports an explicit scripted denial without stdin."""
    assert main(["--decision", "deny", "--workspace", str(tmp_path)]) == 0
    ledgers = list((tmp_path / ".orket" / "quickstart" / "runs").glob("*/ledger.jsonl"))
    assert len(ledgers) == 1
    assert (tmp_path / OUTPUT_RELATIVE_PATH).exists() is False


# Layer: live_truth
@pytest.mark.end_to_end
def test_cli_closed_stdin_returns_structured_refusal(tmp_path: Path, monkeypatch, capsys) -> None:
    """Layer: end-to-end. Proves closed stdin fails promptly with a stable operator-facing error."""

    def _closed_stdin(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _closed_stdin)

    assert main(["--workspace", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "ERROR [E_QUICKSTART_INPUT_REQUIRED]" in captured.err
    assert "Traceback" not in captured.err


def _run_quickstart(
    workspace: Path,
    *args: str,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ORKET_DISABLE_SANDBOX"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "orket.quickstart.governed_action_demo",
            "--workspace",
            str(workspace),
            *args,
        ],
        cwd=workspace,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.end_to_end
@pytest.mark.parametrize(
    ("args", "stdin", "expected_exit", "expected_status", "file_exists"),
    [
        (("--decision", "approve"), None, 0, "action: executed", True),
        (("--decision", "deny"), None, 0, "denied_skipped", False),
        ((), "later\n", 1, "invalid_input_skipped", False),
        ((), "", 2, "E_QUICKSTART_INPUT_REQUIRED", False),
    ],
)
# Layer: live_truth
def test_quickstart_native_process_outcomes(
    tmp_path: Path,
    args: tuple[str, ...],
    stdin: str | None,
    expected_exit: int,
    expected_status: str,
    file_exists: bool,
) -> None:
    """Layer: end-to-end. Proves approval, denial, invalid input, and EOF through a native process."""
    result = _run_quickstart(tmp_path, *args, stdin=stdin)

    assert result.returncode == expected_exit
    assert expected_status in result.stdout + result.stderr
    assert (tmp_path / OUTPUT_RELATIVE_PATH).exists() is file_exists
