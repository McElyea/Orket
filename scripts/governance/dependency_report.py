"""Shared report construction for native dependency commands and the baseline."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.common.git_inventory import GitInventoryError
from scripts.governance.dependency_analysis import analyze_repository
from scripts.governance.dependency_policy import POLICY_PATH, PROJECT_ROOT, load_dependency_policy


def build_dependency_report(*, root: Path = PROJECT_ROOT, policy_path: Path = POLICY_PATH) -> dict:
    report = {
        "schema_version": "dependency_report.v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "collection_ok": False,
        "root": str(root),
        "policy": {"path": str(policy_path)},
        "observed": {},
        "verdict": {"ok": False},
    }
    try:
        policy = load_dependency_policy(policy_path)
        root = root.resolve(strict=True)
        report["policy"] = {
            "path": policy_path.relative_to(root).as_posix() if policy_path.is_relative_to(root) else str(policy_path),
            "sha256": policy.source_sha256,
            "contract": json.loads(policy.source_document),
        }
        report.update(analyze_repository(root, policy))
        report["collection_ok"] = not any(
            r["code"]
            in {"source_parse_or_read_error", "source_changed_during_scan", "source_inventory_changed_during_scan"}
            for r in report["observed"]["analysis_errors"]
        )
    except (OSError, ValueError, TypeError, GitInventoryError) as exc:
        report["verdict"] = {
            "ok": False,
            "analysis_errors": [
                {
                    "code": "dependency_collection_error",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "root": str(root),
                    "policy": str(policy_path),
                }
            ],
        }
    return report


def report_summary(report: dict) -> dict:
    verdict, observed = report["verdict"], report["observed"]
    return {
        "collection_ok": report["collection_ok"],
        "ok": verdict["ok"],
        "files": observed.get("files_scanned", 0),
        "edges": len(observed.get("edges", [])),
        "resolved_dynamic_routes": len(observed.get("resolved_dynamic_routes", [])),
        **{
            name: len(verdict.get(name, []))
            for name in ("violations", "unknown_modules", "analysis_errors", "authority_cycles")
        },
    }
