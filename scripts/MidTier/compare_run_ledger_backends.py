from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare SQLite and append-only protocol run ledger rows for one session id.",
    )
    parser.add_argument("--session-id", required=True, help="Run/session id to compare")
    parser.add_argument("--sqlite-db", required=True, help="Path to SQLite runtime DB")
    parser.add_argument("--protocol-root", required=True, help="Root directory for protocol run ledger files")
    parser.add_argument("--out", default="", help="Optional output JSON path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if parity is not clean")
    return parser


async def _compare(session_id: str, sqlite_db: Path, protocol_root: Path) -> dict:
    sqlite_repo = AsyncRunLedgerRepository(sqlite_db)
    protocol_repo = AsyncProtocolRunLedgerRepository(protocol_root)
    return await compare_run_ledger_rows(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        session_id=session_id,
    )


def _write(payload: dict, out_path: Path | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if out_path is None:
        print(text, end="")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = asyncio.run(
        _compare(
            session_id=str(args.session_id),
            sqlite_db=Path(str(args.sqlite_db)).resolve(),
            protocol_root=Path(str(args.protocol_root)).resolve(),
        )
    )
    out_raw = str(args.out or "").strip()
    out_path = Path(out_raw).resolve() if out_raw else None
    _write(payload, out_path)
    if bool(args.strict) and not bool(payload.get("parity_ok", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
