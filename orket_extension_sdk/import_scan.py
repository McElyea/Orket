from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

ERROR_IMPORT_FORBIDDEN = "E_SDK_IMPORT_FORBIDDEN"
ERROR_SCAN_TARGET_MISSING = "E_SDK_IMPORT_SCAN_TARGET_MISSING"
ERROR_SCAN_TARGET_INVALID = "E_SDK_IMPORT_SCAN_TARGET_INVALID"
ERROR_SCAN_PARSE = "E_SDK_IMPORT_SCAN_PARSE"


def _is_forbidden_import(module_name: str) -> bool:
    return module_name == "orket" or module_name.startswith("orket.")


def _iter_python_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(path for path in target.rglob("*.py") if "__pycache__" not in path.parts)


def _scan_file(source_path: Path, *, root: Path) -> list[dict[str, str]]:
    source = source_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(source_path))
    relative_path = source_path.relative_to(root).as_posix()
    errors: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_import(alias.name):
                    errors.append(
                        {
                            "code": ERROR_IMPORT_FORBIDDEN,
                            "location": f"{relative_path}:{int(node.lineno)}",
                            "message": f"Disallowed import '{alias.name}' in extension source.",
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            module_name = str(node.module or "")
            if module_name and _is_forbidden_import(module_name):
                errors.append(
                    {
                        "code": ERROR_IMPORT_FORBIDDEN,
                        "location": f"{relative_path}:{int(node.lineno)}",
                        "message": f"Disallowed import '{module_name}' in extension source.",
                    }
                )
    return errors


def scan_extension_imports(target: Path) -> dict[str, Any]:
    resolved_target = target.resolve()
    if not resolved_target.exists():
        return {
            "ok": False,
            "target": str(target),
            "scanned_file_count": 0,
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_SCAN_TARGET_MISSING,
                    "location": "target",
                    "message": f"Scan target not found: {target}",
                }
            ],
        }

    if resolved_target.is_file() and resolved_target.suffix.lower() != ".py":
        return {
            "ok": False,
            "target": str(target),
            "scanned_file_count": 0,
            "error_count": 1,
            "errors": [
                {
                    "code": ERROR_SCAN_TARGET_INVALID,
                    "location": "target",
                    "message": f"Scan target file must be a Python file: {target}",
                }
            ],
        }

    root = resolved_target.parent if resolved_target.is_file() else resolved_target
    files = _iter_python_files(resolved_target)
    errors: list[dict[str, str]] = []
    for source_path in files:
        try:
            errors.extend(_scan_file(source_path, root=root))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            relative_path = source_path.relative_to(root).as_posix()
            errors.append(
                {
                    "code": ERROR_SCAN_PARSE,
                    "location": relative_path,
                    "message": str(exc),
                }
            )

    errors.sort(key=lambda item: (item["code"], item["location"], item["message"]))
    return {
        "ok": len(errors) == 0,
        "target": str(target),
        "scanned_file_count": len(files),
        "error_count": len(errors),
        "errors": errors,
    }


def _render_human(result: dict[str, Any]) -> str:
    if bool(result.get("ok")):
        return f"OK: scanned={result.get('scanned_file_count', 0)} target={result.get('target', '')}"
    lines = [f"FAIL ({result.get('error_count', 0)} error(s))"]
    for item in list(result.get("errors") or []):
        lines.append(f"[{item.get('code')}] {item.get('location')}: {item.get('message')}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m orket_extension_sdk.import_scan",
        description="Scan extension Python sources for disallowed internal Orket imports.",
    )
    parser.add_argument("target", nargs="?", default=".", help="Directory or Python file to scan.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = scan_extension_imports(Path(args.target))
    if bool(args.json):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(_render_human(result))
    return 0 if bool(result.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
