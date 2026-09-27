from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.common.git_inventory import GitInventoryError
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.governance.noop_analysis import NoopVisitor
    from scripts.governance.quality_scan_inventory import git_visible_python_files
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.common.git_inventory import GitInventoryError
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
    from scripts.governance.noop_analysis import NoopVisitor
    from scripts.governance.quality_scan_inventory import git_visible_python_files


DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "orket/application",
    "orket/runtime",
    "orket/interfaces",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect no-op functions in critical runtime paths.")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Scan root (repeatable). Defaults to runtime critical roots.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path for findings.",
    )
    return parser.parse_args(argv)


def _collect_noop_findings(path: Path, source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source, filename=str(path))
    visitor = NoopVisitor()
    visitor.visit(tree)
    return [{"path": str(path), **finding} for finding in visitor.findings]


def evaluate_noop_critical_paths(*, roots: list[Path]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    try:
        files = git_visible_python_files(roots)
    except (GitInventoryError, OSError) as exc:
        files = []
        parse_errors.append({"path": "", "error": f"scan_inventory_error:{exc}"})
    if not files and not parse_errors:
        parse_errors.append({"path": "", "error": "scan_files_empty"})
    for path in files:
        try:
            source = path.read_text(encoding="utf-8-sig")
            findings.extend(_collect_noop_findings(path, source))
        except (OSError, SyntaxError, UnicodeError) as exc:
            parse_errors.append({"path": str(path), "error": str(exc)})
    return {
        "schema_version": "1.0",
        "ok": not findings and not parse_errors,
        "roots": [str(root) for root in roots],
        "scanned_files": len(files),
        "findings": findings,
        "parse_errors": parse_errors,
    }


def check_noop_critical_paths(*, roots: list[Path], out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_noop_critical_paths(roots=roots)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    roots = [Path(token).resolve() for token in (args.root or []) if str(token or "").strip()]
    if not roots:
        roots = [Path(path).resolve() for path in DEFAULT_SCAN_ROOTS]
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_noop_critical_paths(roots=roots, out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
