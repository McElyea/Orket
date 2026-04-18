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

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.productflow.productflow_support import build_productflow_engine, resolve_productflow_paths
from scripts.proof.trusted_run_witness_support import (
    DEFAULT_BUNDLE_NAME,
    build_witness_bundle_payload,
    relative_to_repo,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Trusted Run Witness bundle for ProductFlow write_file.")
    parser.add_argument("--run-id", required=True, help="Canonical ProductFlow governed turn-tool run id.")
    parser.add_argument("--workspace-root", default="", help="Optional ProductFlow workspace root override.")
    parser.add_argument("--output", default="", help="Optional stable bundle output path.")
    parser.add_argument("--json", action="store_true", help="Print the persisted bundle.")
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> tuple[dict[str, object], Path]:
    workspace_override = Path(str(args.workspace_root)).resolve() if str(args.workspace_root).strip() else None
    paths = resolve_productflow_paths(workspace_override)
    engine = build_productflow_engine(paths)
    bundle = await build_witness_bundle_payload(paths=paths, engine=engine, run_id=str(args.run_id))
    output = Path(str(args.output)).resolve() if str(args.output).strip() else _default_output(paths, bundle)
    persisted = write_payload_with_diff_ledger(output, bundle)
    return persisted, output


def _default_output(paths: object, bundle: dict[str, object]) -> Path:
    session_id = str(bundle.get("session_id") or "").strip()
    if not session_id:
        raise ValueError("trusted_run_bundle_session_id_required")
    return paths.workspace_root / "runs" / session_id / DEFAULT_BUNDLE_NAME


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    persisted, output = asyncio.run(_run(args))
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('contract_verdict', {}).get('verdict')}",
                    f"run_id={persisted.get('run_id')}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("contract_verdict", {}).get("verdict") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
