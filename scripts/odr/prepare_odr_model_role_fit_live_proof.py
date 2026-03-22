from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.odr.model_role_fit_live_proof import run_model_role_fit_live_proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the locked ODR model-role fit serial experiment.")
    parser.add_argument("--config", help="Optional model-role fit lane config override path.")
    args = parser.parse_args()

    result = asyncio.run(
        run_model_role_fit_live_proof(
            config_path=Path(args.config).resolve() if args.config else None,
        )
    )
    print(
        "Prepared ODR model-role fit artifacts "
        f"bootstrap={result['bootstrap_output']} "
        f"pair_compare={result['pair_compare_output']} "
        f"pair_verdict={result['pair_verdict_output']} "
        f"triple_verdict={result['triple_verdict_output']} "
        f"closeout={result['closeout_output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
