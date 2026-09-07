from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiofiles

from orket.quickstart.ledger import QuickstartLedgerWriter

TOOL_NAME = "write_file"
OUTPUT_RELATIVE_PATH = Path("quickstart_out") / "hello_from_orket.txt"
OUTPUT_CONTENT = "hello from a governed Orket action\n"
LEDGER_RUN_ROOT = Path(".orket") / "quickstart" / "runs"


@dataclass(frozen=True)
class DemoResult:
    run_id: str
    terminal_status: str
    action_executed: bool
    output_path: Path | None
    ledger_path: Path
    verifier_command: str


def generate_run_id() -> str:
    return f"quickstart-{uuid.uuid4().hex[:12]}"


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def mock_model_proposal() -> dict[str, str]:
    return {
        "tool_name": TOOL_NAME,
        "path": OUTPUT_RELATIVE_PATH.as_posix(),
        "content": OUTPUT_CONTENT,
    }


async def run_governed_action_demo(
    *,
    workspace: Path | None = None,
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
    run_id_factory: Callable[[], str] = generate_run_id,
    timestamp_factory: Callable[[], str] = utc_timestamp,
) -> DemoResult:
    root = workspace or Path()
    read_input = input_func or input
    write_output = output_func or print
    run_id = run_id_factory()
    ledger_path = root / LEDGER_RUN_ROOT / run_id / "ledger.jsonl"
    output_path = root / OUTPUT_RELATIVE_PATH
    display_output_path = OUTPUT_RELATIVE_PATH.as_posix()
    display_ledger_path = (LEDGER_RUN_ROOT / run_id / "ledger.jsonl").as_posix()
    ledger = await QuickstartLedgerWriter.create(
        path=ledger_path,
        run_id=run_id,
        timestamp_factory=timestamp_factory,
    )

    await ledger.emit(
        "run_started",
        {
            "demo": "governed_action_quickstart",
            "network_required": False,
            "model": "mock_local_model",
        },
    )

    proposal = mock_model_proposal()
    await ledger.emit("tool_call_proposed", proposal)
    await ledger.emit(
        "approval_requested",
        {
            "tool_name": proposal["tool_name"],
            "path": proposal["path"],
            "status": "waiting_for_operator",
        },
    )

    write_output("GOVERNED ACTION REQUEST")
    write_output(f"tool: {proposal['tool_name']}")
    write_output(f"path: {proposal['path']}")
    write_output("status: waiting_for_operator")
    operator_input = await asyncio.to_thread(read_input, "Approve this action? [a]pprove / [d]eny: ")
    normalized_input = operator_input.strip().lower()

    if normalized_input in {"a", "approve"}:
        terminal_status = "approved_executed"
        await ledger.emit("operator_approved", {"operator_input": normalized_input})
        await _write_text_file(output_path, proposal["content"])
        await _assert_file_content(output_path, proposal["content"])
        await ledger.emit(
            "tool_effect_executed",
            {
                "tool_name": proposal["tool_name"],
                "path": proposal["path"],
                "bytes_written": len(proposal["content"].encode("utf-8")),
            },
        )
        await ledger.emit("run_finished", {"terminal_status": terminal_status})
        result = DemoResult(
            run_id=run_id,
            terminal_status=terminal_status,
            action_executed=True,
            output_path=output_path,
            ledger_path=ledger_path,
            verifier_command=_verifier_command(display_ledger_path),
        )
    elif normalized_input in {"d", "deny"}:
        terminal_status = "denied_skipped"
        await ledger.emit("operator_denied", {"operator_input": normalized_input})
        await ledger.emit(
            "tool_effect_skipped",
            {
                "tool_name": proposal["tool_name"],
                "path": proposal["path"],
                "reason": "operator_denied",
            },
        )
        await ledger.emit("run_finished", {"terminal_status": terminal_status})
        result = DemoResult(
            run_id=run_id,
            terminal_status=terminal_status,
            action_executed=False,
            output_path=None,
            ledger_path=ledger_path,
            verifier_command=_verifier_command(display_ledger_path),
        )
    else:
        terminal_status = "invalid_input_skipped"
        await ledger.emit("operator_input_invalid", {"operator_input": normalized_input})
        await ledger.emit(
            "tool_effect_skipped",
            {
                "tool_name": proposal["tool_name"],
                "path": proposal["path"],
                "reason": "invalid_operator_input",
            },
        )
        await ledger.emit("run_finished", {"terminal_status": terminal_status})
        result = DemoResult(
            run_id=run_id,
            terminal_status=terminal_status,
            action_executed=False,
            output_path=None,
            ledger_path=ledger_path,
            verifier_command=_verifier_command(display_ledger_path),
        )

    _print_result(result, display_output_path, display_ledger_path, write_output)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the local governed-action quickstart and record a verifiable ledger."
    )
    parser.add_argument(
        "--decision",
        choices=("approve", "deny"),
        help="Supply a scripted operator decision; omit for an interactive prompt.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(),
        help="Directory where quickstart output and ledger artifacts are written.",
    )
    args = parser.parse_args(argv)
    input_func = (lambda _prompt: args.decision) if args.decision else None
    try:
        result = asyncio.run(
            run_governed_action_demo(
                workspace=args.workspace,
                input_func=input_func,
            )
        )
    except EOFError:
        print(
            "ERROR [E_QUICKSTART_INPUT_REQUIRED]: no operator decision was available; "
            "rerun with --decision approve or --decision deny.",
            file=sys.stderr,
        )
        return 2
    return 1 if result.terminal_status == "invalid_input_skipped" else 0


async def _write_text_file(path: Path, content: str) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as output_file:
        await output_file.write(content)


async def _assert_file_content(path: Path, expected_content: str) -> None:
    async with aiofiles.open(path, encoding="utf-8") as output_file:
        observed = await output_file.read()
    if observed != expected_content:
        raise RuntimeError(f"file write verification failed for {path.as_posix()}")


def _print_result(
    result: DemoResult,
    display_output_path: str,
    display_ledger_path: str,
    output_func: Callable[[str], None],
) -> None:
    output_func("")
    if result.action_executed:
        output_func("action: executed")
        output_func(f"output_file: {display_output_path}")
    else:
        output_func(f"action: skipped ({result.terminal_status})")
    output_func(f"ledger: {display_ledger_path}")
    output_func(f"verify: {result.verifier_command}")


def _verifier_command(ledger_path: str) -> str:
    return f"python -m orket.quickstart.verify_ledger {ledger_path}"


if __name__ == "__main__":
    raise SystemExit(main())
