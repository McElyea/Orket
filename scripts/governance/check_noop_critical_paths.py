from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import sys

    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


DEFAULT_SCAN_ROOTS: tuple[str, ...] = (
    "orket/application",
    "orket/runtime",
    "orket/interfaces",
)
_SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__"}


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


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return str(node.attr or "")
    return ""


def _is_abstract_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_decorator_name(decorator) == "abstractmethod" for decorator in node.decorator_list)


def _is_noop_body(body: list[ast.stmt]) -> str | None:
    statements = [stmt for stmt in body if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Constant)]
    if len(statements) == 1 and isinstance(statements[0], ast.Pass):
        return "pass_statement"
    if len(statements) == 1 and isinstance(statements[0], ast.Return):
        if statements[0].value is None:
            return "return_none"
        if isinstance(statements[0].value, ast.Constant) and statements[0].value.value is None:
            return "return_none"
    if len(body) == 1 and isinstance(body[0], ast.Expr):
        expr = body[0].value
        if isinstance(expr, ast.Constant) and expr.value is Ellipsis:
            return "ellipsis"
    return None


def _collect_noop_findings(path: Path, source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source, filename=str(path))
    findings: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_abstract_function(node):
            continue
        reason = _is_noop_body(node.body)
        if reason is None:
            continue
        findings.append(
            {
                "path": str(path),
                "line": int(node.lineno),
                "name": str(node.name or ""),
                "reason": reason,
                "async": isinstance(node, ast.AsyncFunctionDef),
            }
        )
    return findings


def evaluate_noop_critical_paths(*, roots: list[Path]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    files = _iter_python_files(roots)
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            findings.extend(_collect_noop_findings(path, source))
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


def check_noop_critical_paths(*, roots: list[Path], out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_noop_critical_paths(roots=roots)
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or [])
    roots = [Path(token).resolve() for token in (args.root or []) if str(token or "").strip()]
    if not roots:
        roots = [Path(path).resolve() for path in DEFAULT_SCAN_ROOTS]
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_noop_critical_paths(roots=roots, out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
