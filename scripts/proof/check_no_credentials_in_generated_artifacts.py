#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.trusted_terraform_plan_decision_contract import now_utc_iso, relative_to_repo

CHECK_SCHEMA_VERSION = "generated_artifact_credential_scan.v1"
DEFAULT_SCAN_ROOT = REPO_ROOT / "workspace" / "trusted_terraform_live_setup"
DEFAULT_OUTPUT = DEFAULT_SCAN_ROOT / "credential-scan.json"
_FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"aws_secret_access_key\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"AWS_SECRET_ACCESS_KEY\s*=\s*['\"]?[A-Za-z0-9/+=]{20,}['\"]?"),
    re.compile(r"AWS_SESSION_TOKEN\s*=\s*['\"]?[A-Za-z0-9/+=]{20,}['\"]?"),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY"),
]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan generated artifacts for captured credential values.")
    parser.add_argument("--scan-root", default=str(DEFAULT_SCAN_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true", help="Print persisted scan JSON.")
    return parser.parse_args(argv)


def scan_generated_artifacts(*, scan_root: Path) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    if not scan_root.exists():
        return _report(scan_root, "blocked", "environment blocker", [{"path": relative_to_repo(scan_root), "reason": "scan_root_missing"}])
    for path in _iter_scan_files(scan_root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in _FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(text):
                hits.append({"path": relative_to_repo(path), "reason": pattern.pattern})
    return _report(scan_root, "primary" if not hits else "blocked", "success" if not hits else "failure", hits)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = scan_generated_artifacts(scan_root=Path(str(args.scan_root)).resolve())
    output = Path(str(args.output)).resolve()
    persisted = write_payload_with_diff_ledger(output, payload)
    if args.json:
        print(json.dumps(persisted, indent=2, ensure_ascii=True))
    else:
        print(
            " ".join(
                [
                    f"observed_result={persisted.get('observed_result')}",
                    f"hit_count={len(persisted.get('credential_hits') or [])}",
                    f"output={relative_to_repo(output)}",
                ]
            )
        )
    return 0 if persisted.get("observed_result") == "success" else 1


def _iter_scan_files(scan_root: Path) -> list[Path]:
    return [
        path
        for path in scan_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".json", ".ps1", ".template", ".env", ".md", ".txt"}
    ]


def _report(scan_root: Path, observed_path: str, observed_result: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": CHECK_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": observed_path,
        "observed_result": observed_result,
        "scan_root": relative_to_repo(scan_root),
        "credential_values_recorded": bool(hits),
        "credential_hits": hits,
        "allowed_template_names": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
