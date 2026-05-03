#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof.outward_run_witness_builder import build_outward_run_witness_package
from scripts.proof.outward_run_witness_contract import COMPARE_SCOPE


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit an outward_run_witness_package.v1 from persisted outward evidence.")
    parser.add_argument("--run-id", required=True, help="Outward run id to package.")
    parser.add_argument("--scope", default=COMPARE_SCOPE, help="Admitted outward run compare scope.")
    parser.add_argument("--output", required=True, help="Package output directory.")
    parser.add_argument("--db-path", default=".orket/durable/db/control_plane_records.sqlite3", help="Outward pipeline SQLite path.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root used by the outward execution.")
    parser.add_argument("--json", action="store_true", help="Print the package emission result as JSON.")
    return parser.parse_args(argv)


async def _amain(argv: list[str]) -> int:
    args = _parse_args(argv)
    result = await build_outward_run_witness_package(
        db_path=Path(str(args.db_path)).resolve(),
        workspace_root=Path(str(args.workspace_root)).resolve(),
        run_id=str(args.run_id),
        output_dir=Path(str(args.output)).resolve(),
        scope=str(args.scope or COMPARE_SCOPE),
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(f"package={result['package_path']} run_id={result['run_id']} compare_scope={result['compare_scope']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
