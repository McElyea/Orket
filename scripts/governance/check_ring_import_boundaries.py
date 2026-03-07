from __future__ import annotations

import argparse
import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "orket"
DEFAULT_OUT = PROJECT_ROOT / "benchmarks" / "results" / "ring_import_boundary_check.json"
DEFAULT_FORBIDDEN_PREFIXES = (
    "orket.runtime",
    "orket.application.workflows",
)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _module_name(path: Path, root: Path) -> str:
    rel = path.with_suffix("").relative_to(root)
    return ".".join(rel.parts)


def _classify_ring(path: Path, root: Path) -> str | None:
    rel_parts = [part.lower() for part in path.relative_to(root).parts]
    if "compatibility" in rel_parts:
        return "compatibility"
    if "experimental" in rel_parts:
        return "experimental"
    return None


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def check_ring_import_boundaries(*, root: Path, forbidden_prefixes: tuple[str, ...]) -> dict[str, object]:
    violations: list[dict[str, str]] = []
    files_scanned = 0
    ring_files_scanned = 0

    for py_file in _iter_python_files(root):
        files_scanned += 1
        ring = _classify_ring(py_file, root)
        if ring is None:
            continue
        ring_files_scanned += 1
        source_module = _module_name(py_file, root)
        for imported in _imports(py_file):
            for prefix in forbidden_prefixes:
                if imported == prefix or imported.startswith(prefix + "."):
                    violations.append(
                        {
                            "source_module": source_module,
                            "ring": ring,
                            "imported_module": imported,
                            "forbidden_prefix": prefix,
                        }
                    )
                    break

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "forbidden_prefixes": list(forbidden_prefixes),
        "files_scanned": files_scanned,
        "ring_files_scanned": ring_files_scanned,
        "violation_count": len(violations),
        "violations": violations,
        "ok": len(violations) == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enforce ring import boundaries for compatibility/experimental code paths.",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--forbidden-prefix",
        action="append",
        default=[],
        help="Additional forbidden import prefix. Can be repeated.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    forbidden = tuple(str(value).strip() for value in args.forbidden_prefix if str(value).strip())
    if not forbidden:
        forbidden = DEFAULT_FORBIDDEN_PREFIXES

    payload = check_ring_import_boundaries(root=root, forbidden_prefixes=forbidden)
    out_path = args.out.resolve()
    write_payload_with_diff_ledger(out_path, payload)

    if not bool(payload.get("ok")):
        for violation in payload.get("violations", []):
            if not isinstance(violation, dict):
                continue
            print(
                "ring import boundary violation: "
                f"{violation.get('source_module')} -> {violation.get('imported_module')}"
            )
        raise SystemExit(1)

    print(json.dumps({"status": "ok", "violations": 0}, ensure_ascii=True))


if __name__ == "__main__":
    main()
