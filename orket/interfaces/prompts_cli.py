"""Prompt command argument parsing and output; application owns file operations."""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import sys
from pathlib import Path
from typing import Any

from orket.application.services.prompt_asset_service import PromptAssetService


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt asset tooling for Orket.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root containing model/core assets.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List prompt assets.")
    p_list.add_argument("--kind", choices=["all", "role", "dialect"], default="all")
    p_list.add_argument("--status", default="")
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show one prompt asset by id.")
    p_show.add_argument("--id", required=True, help="Prompt id: role.<name> or dialect.<name>")

    p_validate = sub.add_parser("validate", help="Validate prompt asset contracts.")
    p_validate.add_argument("--json", action="store_true")

    p_resolve = sub.add_parser("resolve", help="Resolve effective prompt for role+dialect.")
    p_resolve.add_argument("--role", required=True)
    p_resolve.add_argument("--dialect", required=True)
    p_resolve.add_argument("--selection-policy", choices=["stable", "canary", "exact"], default="stable")
    p_resolve.add_argument("--version-exact", default="")
    p_resolve.add_argument("--strict", action="store_true", default=True)
    p_resolve.add_argument("--profile", default="default")
    p_resolve.add_argument("--include-prompt", action="store_true")

    p_diff = sub.add_parser("diff", help="Diff resolved prompt outputs across policy/version selections.")
    p_diff.add_argument("--role", required=True)
    p_diff.add_argument("--dialect", required=True)
    p_diff.add_argument("--left-policy", choices=["stable", "canary", "exact"], default="stable")
    p_diff.add_argument("--left-version-exact", default="")
    p_diff.add_argument("--right-policy", choices=["stable", "canary", "exact"], default="canary")
    p_diff.add_argument("--right-version-exact", default="")
    p_diff.add_argument("--strict", action="store_true", default=True)

    p_new = sub.add_parser("new", help="Create new prompt version metadata entry.")
    p_new.add_argument("--id", required=True)
    p_new.add_argument("--version", required=True)
    p_new.add_argument("--status", choices=sorted(PromptAssetService.statuses), default="draft")
    p_new.add_argument("--notes", default="")
    p_new.add_argument("--apply", action="store_true")

    p_promote = sub.add_parser("promote", help="Promote prompt status.")
    p_promote.add_argument("--id", required=True)
    p_promote.add_argument("--status", choices=sorted(PromptAssetService.statuses), default="stable")
    p_promote.add_argument("--notes", default="")
    p_promote.add_argument("--promotion-report", default="", help="Optional JSON report with pass/blockers.")
    p_promote.add_argument("--apply", action="store_true")

    p_deprecate = sub.add_parser("deprecate", help="Deprecate a prompt.")
    p_deprecate.add_argument("--id", required=True)
    p_deprecate.add_argument("--notes", default="")
    p_deprecate.add_argument("--apply", action="store_true")

    p_sla = sub.add_parser(
        "enforce-sla", help="Enforce candidate prompt SLA by renewing or auto-deprecating stale candidates."
    )
    p_sla.add_argument("--max-candidate-age-days", type=int, default=14)
    p_sla.add_argument(
        "--renew", action="append", default=[], help="Prompt id to keep in candidate via explicit renewal."
    )
    p_sla.add_argument("--as-of", default="", help="Optional YYYY-MM-DD anchor date.")
    p_sla.add_argument("--apply", action="store_true")
    return parser


async def _resolve(service: PromptAssetService, args: argparse.Namespace) -> int:
    if args.cmd == "resolve":
        resolved = await service.execute("resolve", role=args.role, dialect=args.dialect,
            selection_policy=args.selection_policy, version_exact=args.version_exact,
            strict=bool(args.strict), profile=args.profile)
        payload = {"metadata": resolved["metadata"], "layers": resolved["layers"]}
        if args.include_prompt:
            payload["prompt"] = resolved["prompt"]
        _print_json(payload)
        return 0
    left = await service.execute("resolve", role=args.role, dialect=args.dialect,
        selection_policy=args.left_policy, version_exact=args.left_version_exact, strict=bool(args.strict))
    right = await service.execute("resolve", role=args.role, dialect=args.dialect,
        selection_policy=args.right_policy, version_exact=args.right_version_exact, strict=bool(args.strict))
    diff = list(difflib.unified_diff(str(left["prompt"] or "").splitlines(), str(right["prompt"] or "").splitlines(),
        fromfile=f"{args.left_policy}:{args.left_version_exact or 'auto'}",
        tofile=f"{args.right_policy}:{args.right_version_exact or 'auto'}", lineterm=""))
    _print_json({"left_metadata": left["metadata"], "right_metadata": right["metadata"], "prompt_diff": diff})
    return 0


def _print_lint(lint: dict[str, Any], *, as_json: bool) -> int:
    payload = {"ok": lint["ok"], "error_count": lint["error_count"], "warning_count": lint["warning_count"],
               "errors": [item["message"] for item in lint["errors"]],
               "warnings": [item["message"] for item in lint["warnings"]]}
    if as_json or lint["error_count"]:
        _print_json(payload)
    if lint["error_count"]:
        return 1
    print("Prompt assets valid.")
    return 0


async def _run(service: PromptAssetService, args: argparse.Namespace, report_path: str | None) -> int:
    if args.cmd == "list":
        rows = await service.execute("list", kind=args.kind, status=args.status)
        if args.json:
            _print_json({"count": len(rows), "items": rows})
        else:
            for row in rows:
                print(f"{row['id']}  kind={row['kind']} status={row['status']} version={row['version']} path={row['path']}")
        return 0
    if args.cmd == "show":
        _print_json(await service.execute("show", prompt_id=args.id))
        return 0
    if args.cmd == "validate":
        return _print_lint(await service.execute("lint"), as_json=bool(args.json))
    if args.cmd in {"resolve", "diff"}:
        return await _resolve(service, args)
    if args.cmd in {"new", "promote", "deprecate"}:
        result = await service.execute("update", prompt_id=args.id, mode=args.cmd,
            version=getattr(args, "version", ""), status=getattr(args, "status", ""), notes=args.notes,
            promotion_report_path=report_path, apply_changes=bool(args.apply))
        _print_json(result)
        return 0
    result = await service.execute("enforce_sla", max_candidate_age_days=args.max_candidate_age_days,
        renew_ids=args.renew, as_of=args.as_of or None, apply_changes=bool(args.apply))
    _print_json(result)
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.root).absolute()
    report = str(getattr(args, "promotion_report", "") or "").strip()
    report_path = str(Path(report).absolute()) if report else None
    try:
        return asyncio.run(_run(PromptAssetService(root), args, report_path))
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(f"Prompt command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
