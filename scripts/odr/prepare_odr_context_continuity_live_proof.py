from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.odr.context_continuity_live_proof import run_context_continuity_live_proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the locked ContextContinuity control, V0, and V1 live proof.")
    parser.add_argument("--config", help="Optional lane config override path.")
    args = parser.parse_args()

    result = asyncio.run(
        run_context_continuity_live_proof(
            config_path=Path(args.config).resolve() if args.config else None,
        )
    )
    print(
        "Prepared ContextContinuity live proof artifacts "
        f"inspectability={result['inspectability_output']} "
        f"compare={result['compare_output']} "
        f"verdict={result['verdict_output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
