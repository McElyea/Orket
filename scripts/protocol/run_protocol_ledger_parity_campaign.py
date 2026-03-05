from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare SQLite and protocol run-ledger parity across a campaign of session ids.",
    )
    parser.add_argument("--sqlite-db", required=True, help="Path to SQLite run ledger DB.")
    parser.add_argument("--protocol-root", required=True, help="Workspace root containing runs/<session_id>/events.log.")
    parser.add_argument("--session-id", action="append", default=[], help="Optional session id filter (repeatable).")
    parser.add_argument("--discover-limit", type=int, default=200, help="Max SQLite sessions discovered when --session-id is omitted.")
    parser.add_argument("--max-mismatches", type=int, default=0, help="Strict-mode mismatch threshold.")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when mismatch_count exceeds --max-mismatches.")
    return parser


def _write(payload: dict[str, Any], *, out_path: Path | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if out_path is None:
        print(text, end="")
        return
    write_payload_with_diff_ledger(out_path, payload)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    sqlite_db = Path(str(args.sqlite_db)).resolve()
    protocol_root = Path(str(args.protocol_root)).resolve()
    return await compare_protocol_ledger_parity_campaign(
        sqlite_db=sqlite_db,
        protocol_root=protocol_root,
        session_ids=list(args.session_id or []),
        discover_limit=int(args.discover_limit),
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = asyncio.run(_run(args))
    out_raw = str(args.out or "").strip()
    out_path = Path(out_raw).resolve() if out_raw else None
    _write(payload, out_path=out_path)

    if bool(args.strict):
        allowed_mismatches = max(0, int(args.max_mismatches))
        mismatches = int(payload.get("mismatch_count") or 0)
        if mismatches > allowed_mismatches:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
