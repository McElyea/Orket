# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.gitea_state_pilot import collect_gitea_state_pilot_inputs
from orket.application.services.state_reconciliation_service import StateReconciliationService
from orket.runtime_paths import resolve_runtime_db_path
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare card state between SQLite and Gitea state backends.")
    parser.add_argument("--card-id", action="append", default=[], help="Card id/Gitea issue number to compare.")
    parser.add_argument(
        "--out",
        default="benchmarks/results/gitea/state_reconciliation.json",
        help="Stable JSON output artifact path.",
    )
    parser.add_argument("--require-clean", action="store_true", help="Exit non-zero when conflicts are found.")
    return parser.parse_args()


def _build_gitea_adapter(inputs: dict[str, Any]) -> GiteaStateAdapter:
    return GiteaStateAdapter(
        base_url=str(inputs.get("gitea_url") or ""),
        token=str(inputs.get("gitea_token") or ""),
        owner=str(inputs.get("gitea_owner") or ""),
        repo=str(inputs.get("gitea_repo") or ""),
    )


async def _run(card_ids: list[str]) -> dict[str, Any]:
    inputs = collect_gitea_state_pilot_inputs()
    service = StateReconciliationService(
        sqlite_cards=AsyncCardRepository(resolve_runtime_db_path()),
        gitea_cards=_build_gitea_adapter(inputs),
        workspace=PROJECT_ROOT,
    )
    return await service.reconcile(card_ids)


def main() -> int:
    args = _parse_args()
    payload = asyncio.run(_run(list(args.card_id or [])))
    persisted = write_payload_with_diff_ledger(Path(args.out), payload)
    print(json.dumps(persisted, indent=2, ensure_ascii=False))
    if bool(args.require_clean) and not bool(payload.get("ok")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
