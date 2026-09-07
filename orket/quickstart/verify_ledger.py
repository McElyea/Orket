from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from orket.quickstart.ledger import verify_ledger_file


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify an Orket quickstart hash-chained JSONL ledger.")
    parser.add_argument("ledger_path", help="Path to .orket/quickstart/runs/<run_id>/ledger.jsonl")
    return parser


async def async_main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    ledger_path = Path(args.ledger_path)
    result = await verify_ledger_file(ledger_path)

    if result.valid:
        sys.stdout.write(
            "Ledger verification succeeded: "
            f"path={ledger_path.as_posix()} events={result.event_count} "
            f"run_id={result.run_id} final_event_hash={result.final_event_hash}\n"
        )
        return 0

    sys.stderr.write(f"Ledger verification failed: path={ledger_path.as_posix()}\n")
    for error in result.errors:
        sys.stderr.write(f"- {error}\n")
    return 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
