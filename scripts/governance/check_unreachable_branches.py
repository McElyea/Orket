from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "orket/application",
    "orket/runtime",
    "orket/interfaces",
)
_SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__"}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect statically unreachable branches.")
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


def _iter_python_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in _SKIP_PARTS for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _constant_bool_value(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return bool(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        inner = _constant_bool_value(node.operand)
        if inner is None:
            return None
        return not inner
    return None


def _is_type_checking_guard(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TYPE_CHECKING"
    if isinstance(node, ast.Attribute):
        return str(node.attr or "") == "TYPE_CHECKING"
    return False


def _collect_unreachable_findings(path: Path, source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source, filename=str(path))
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            if _is_type_checking_guard(node.test):
                continue
            value = _constant_bool_value(node.test)
            if value is False and node.body:
                findings.append(
                    {
                        "path": str(path),
                        "line": int(node.body[0].lineno),
                        "kind": "if_body_unreachable",
                        "condition_line": int(node.lineno),
                    }
                )
            if value is True and node.orelse:
                findings.append(
                    {
                        "path": str(path),
                        "line": int(node.orelse[0].lineno),
                        "kind": "if_else_unreachable",
                        "condition_line": int(node.lineno),
                    }
                )
        if isinstance(node, ast.While):
            value = _constant_bool_value(node.test)
            if value is False and node.body:
                findings.append(
                    {
                        "path": str(path),
                        "line": int(node.body[0].lineno),
                        "kind": "while_body_unreachable",
                        "condition_line": int(node.lineno),
                    }
                )
    return findings


def evaluate_unreachable_branches(*, roots: list[Path]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    files = _iter_python_files(roots)
    for path in files:
        try:
            source = path.read_text(encoding="utf-8-sig")
            findings.extend(_collect_unreachable_findings(path, source))
        except (OSError, SyntaxError) as exc:
            parse_errors.append({"path": str(path), "error": str(exc)})

    return {
        "schema_version": "1.0",
        "ok": not findings and not parse_errors,
        "roots": [str(root) for root in roots],
        "scanned_files": len(files),
        "findings": findings,
        "parse_errors": parse_errors,
    }


def check_unreachable_branches(*, roots: list[Path], out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_unreachable_branches(roots=roots)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    roots = [Path(token).resolve() for token in (args.root or []) if str(token or "").strip()]
    if not roots:
        roots = [Path(path).resolve() for path in DEFAULT_SCAN_ROOTS]
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_unreachable_branches(roots=roots, out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
