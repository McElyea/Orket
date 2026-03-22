from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.odr.round_cap_probe import run_round_cap_probe


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the locked ODR round-cap probe.")
    parser.add_argument("--config", help="Optional round-cap probe lane config override path.")
    args = parser.parse_args()
    result = asyncio.run(run_round_cap_probe(config_path=Path(args.config).resolve() if args.config else None))
    print(
        "Prepared ODR round-cap probe artifacts "
        f"bootstrap={result['bootstrap_output']} "
        f"compare={result['compare_output']} "
        f"verdict={result['verdict_output']} "
        f"closeout={result['closeout_output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
