#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof.trust_handoff_emitter import emit_trust_handoff_package


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit a Packet 1 trust handoff envelope package.")
    parser.add_argument("--source-run-id", required=True, help="Committed source outward run id.")
    parser.add_argument("--target-agent-id", required=True, help="Target agent id expected by the package.")
    parser.add_argument("--scope-id", required=True, help="Policy compatibility scope id.")
    parser.add_argument("--out", required=True, help="Output package directory.")
    parser.add_argument("--source-package", help="Existing outward_run_witness_package.v1 source package.")
    parser.add_argument("--json", action="store_true", help="Print package emission result as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    result = emit_trust_handoff_package(
        source_run_id=str(args.source_run_id),
        target_agent_id=str(args.target_agent_id),
        scope_id=str(args.scope_id),
        out_dir=Path(str(args.out)),
        source_package=Path(str(args.source_package)) if args.source_package else None,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"package={result['package_path']}",
                    f"source_run_id={result['source_run_id']}",
                    f"target_agent_id={result['target_agent_id']}",
                    f"scope_id={result['scope_id']}",
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
