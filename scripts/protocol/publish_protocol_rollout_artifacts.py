from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign
from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish protocol-governed rollout evidence bundle (replay campaign + ledger parity campaign).",
    )
    parser.add_argument("--workspace-root", default=".", help="Workspace root used for default path resolution.")
    parser.add_argument("--runs-root", default="", help="Optional override for runs root.")
    parser.add_argument("--sqlite-db", default="", help="Optional override for SQLite run ledger DB path.")
    parser.add_argument("--run-id", action="append", default=[], help="Optional replay campaign run id filter (repeatable).")
    parser.add_argument("--baseline-run-id", default="", help="Optional replay campaign baseline run id.")
    parser.add_argument("--session-id", action="append", default=[], help="Optional parity campaign session id filter (repeatable).")
    parser.add_argument("--discover-limit", type=int, default=200, help="Parity campaign SQLite discovery limit.")
    parser.add_argument("--out-dir", default="docs/projects/archive/protocol-governed/artifacts", help="Output artifact directory.")
    parser.add_argument("--allow-missing-sqlite", action="store_true", help="Allow publishing even when SQLite DB is absent.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on replay/parity mismatches.")
    return parser


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, *, bundle: dict[str, Any]) -> None:
    replay = dict(bundle.get("replay_campaign") or {})
    parity = dict(bundle.get("ledger_parity_campaign") or {})
    parity_status = str(parity.get("status") or "ok")
    lines = [
        "# Protocol Rollout Evidence Bundle",
        "",
        f"- generated_at: `{bundle.get('generated_at')}`",
        f"- bundle_digest: `{bundle.get('bundle_digest')}`",
        f"- replay_all_match: `{replay.get('all_match')}`",
        f"- replay_mismatch_count: `{replay.get('mismatch_count')}`",
        f"- parity_status: `{parity_status}`",
        f"- parity_all_match: `{parity.get('all_match')}`",
        f"- parity_mismatch_count: `{parity.get('mismatch_count')}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resolve_path(*, workspace_root: Path, override: str, default_suffix: Path) -> Path:
    value = str(override or "").strip()
    if value:
        return Path(value).resolve()
    return (workspace_root / default_suffix).resolve()


async def _build_bundle(args: argparse.Namespace) -> dict[str, Any]:
    workspace_root = Path(str(args.workspace_root)).resolve()
    runs_root = _resolve_path(
        workspace_root=workspace_root,
        override=str(args.runs_root),
        default_suffix=Path("runs"),
    )
    sqlite_db = _resolve_path(
        workspace_root=workspace_root,
        override=str(args.sqlite_db),
        default_suffix=Path(".orket") / "durable" / "db" / "orket_persistence.db",
    )
    replay_campaign = compare_protocol_determinism_campaign(
        runs_root=runs_root,
        run_ids=list(args.run_id or []),
        baseline_run_id=str(args.baseline_run_id or "").strip() or None,
    )

    parity_campaign: dict[str, Any]
    if sqlite_db.exists():
        parity_campaign = await compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite_db,
            protocol_root=workspace_root,
            session_ids=list(args.session_id or []),
            discover_limit=max(0, int(args.discover_limit)),
        )
        parity_campaign["status"] = "ok"
    else:
        parity_campaign = {
            "status": "sqlite_missing",
            "sqlite_db": str(sqlite_db),
            "all_match": False,
            "mismatch_count": 0,
            "candidate_count": 0,
        }
        if not bool(args.allow_missing_sqlite):
            raise ValueError(f"SQLite run ledger database not found: {sqlite_db}")

    bundle_seed = {
        "replay_campaign": replay_campaign,
        "ledger_parity_campaign": parity_campaign,
    }
    bundle_digest = hash_canonical_json(bundle_seed)

    strict_ok = bool(replay_campaign.get("all_match", False))
    if str(parity_campaign.get("status") or "ok") == "ok":
        strict_ok = strict_ok and bool(parity_campaign.get("all_match", False))
    elif not bool(args.allow_missing_sqlite):
        strict_ok = False

    return {
        "schema_version": "protocol_rollout_bundle.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "bundle_digest": bundle_digest,
        "workspace_root": str(workspace_root),
        "runs_root": str(runs_root),
        "sqlite_db": str(sqlite_db),
        "replay_campaign": replay_campaign,
        "ledger_parity_campaign": parity_campaign,
        "strict_ok": strict_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    bundle = asyncio.run(_build_bundle(args))

    out_dir = Path(str(args.out_dir)).resolve()
    short_digest = str(bundle.get("bundle_digest") or "")[:16]
    versioned_json = out_dir / f"protocol_rollout_bundle_{short_digest}.json"
    latest_json = out_dir / "protocol_rollout_bundle.latest.json"
    latest_md = out_dir / "protocol_rollout_bundle.latest.md"

    _write_json(versioned_json, bundle)
    _write_json(latest_json, bundle)
    _write_markdown(latest_md, bundle=bundle)

    payload = {
        "bundle_digest": bundle.get("bundle_digest"),
        "strict_ok": bundle.get("strict_ok"),
        "out_dir": str(out_dir),
        "versioned_json": str(versioned_json),
        "latest_json": str(latest_json),
        "latest_markdown": str(latest_md),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if bool(args.strict) and not bool(bundle.get("strict_ok", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
