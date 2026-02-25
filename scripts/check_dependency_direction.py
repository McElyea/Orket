from __future__ import annotations

import ast
import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Tuple

from dependency_policy import POLICY_PATH, PROJECT_ROOT, load_dependency_policy


OUTPUT_PATH = PROJECT_ROOT / "benchmarks" / "results" / "dependency_direction_check.json"


def _module_from_path(path: Path) -> str:
    rel = path.with_suffix("").relative_to(PROJECT_ROOT)
    return ".".join(rel.parts)


def _imports_for_file(path: Path) -> List[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _is_violation(src_layer: str, dst_layer: str, *, forbidden_edges: set[tuple[str, str]]) -> bool:
    return (src_layer, dst_layer) in forbidden_edges


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce dependency direction policy.")
    parser.add_argument("--out", type=Path, default=OUTPUT_PATH, help="Output JSON report path.")
    parser.add_argument(
        "--legacy-edge-enforcement",
        choices=("warn", "fail"),
        default="warn",
        help="How to enforce legacy-edge budget overruns.",
    )
    parser.add_argument(
        "--legacy-edge-max",
        type=int,
        default=None,
        help="Optional override for legacy edge budget max.",
    )
    args = parser.parse_args()

    policy = load_dependency_policy()
    violations: List[Tuple[str, str]] = []
    unknown_modules: set[str] = set()
    scanned_files = 0
    layer_edges: Counter[tuple[str, str]] = Counter()
    forbidden_edges = set(policy.forbidden_edges)
    scanned_roots = [PROJECT_ROOT / root for root in policy.scan_roots]

    for root in scanned_roots:
        if not root.exists():
            print(f"Dependency policy scan root missing: {root}")
            raise SystemExit(1)
        if not any(root.rglob("*.py")):
            print(f"Dependency policy scan root has no python files: {root}")
            raise SystemExit(1)

    for root in scanned_roots:
        for py_path in root.rglob("*.py"):
            if "__pycache__" in py_path.parts:
                continue
            scanned_files += 1
            src_module = _module_from_path(py_path)
            try:
                src_layer = policy.layer_for_module(src_module)
            except ValueError:
                unknown_modules.add(src_module)
                continue

            for imported in _imports_for_file(py_path):
                if not imported.startswith("orket."):
                    continue
                try:
                    dst_layer = policy.layer_for_module(imported)
                except ValueError:
                    unknown_modules.add(imported)
                    continue
                layer_edges[(src_layer, dst_layer)] += 1
                if _is_violation(
                    src_layer,
                    dst_layer,
                    forbidden_edges=forbidden_edges,
                ):
                    violations.append((src_module, imported))

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "ok": not violations and not unknown_modules,
        "policy": {
            "path": str(POLICY_PATH.relative_to(PROJECT_ROOT)),
            "policy_id": policy.policy_id,
            "schema_version": policy.schema_version,
            "scan_roots": list(policy.scan_roots),
            "forbidden_edges": [
                {"source_layer": src, "target_layer": dst}
                for src, dst in sorted(policy.forbidden_edges)
            ],
        },
        "scan": {
            "files_scanned": scanned_files,
            "roots": [str(root.relative_to(PROJECT_ROOT)) for root in scanned_roots],
        },
        "unknown_modules": sorted(unknown_modules),
        "violations": [
            {"source_module": src, "target_module": dst}
            for src, dst in sorted(set(violations))
        ],
        "layer_edges": [
            {"source_layer": src, "target_layer": dst, "count": count}
            for (src, dst), count in sorted(layer_edges.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
        ],
    }
    legacy_edge_count = sum(
        count for (src, dst), count in layer_edges.items() if src == "legacy" or dst == "legacy"
    )
    legacy_edge_max = args.legacy_edge_max if args.legacy_edge_max is not None else policy.legacy_edge_budget_max
    budget_exceeded = legacy_edge_max is not None and legacy_edge_count > legacy_edge_max
    report["legacy_edge_budget"] = {
        "actual_edges": legacy_edge_count,
        "max_edges": legacy_edge_max,
        "enforcement": args.legacy_edge_enforcement,
        "exceeded": budget_exceeded,
    }
    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    try:
        out_label = out_path.relative_to(PROJECT_ROOT)
    except ValueError:
        out_label = out_path
    print(f"Wrote {out_label}")

    if unknown_modules:
        print("Dependency direction check failed: unknown module classifications found.")
        for module in sorted(unknown_modules):
            print(f"- unknown: {module}")
        raise SystemExit(1)

    if budget_exceeded:
        message = (
            f"Legacy edge budget exceeded: {legacy_edge_count} > {legacy_edge_max} "
            f"(mode={args.legacy_edge_enforcement})"
        )
        if args.legacy_edge_enforcement == "fail":
            print(f"Dependency direction check failed: {message}")
            raise SystemExit(1)
        print(f"Dependency direction warning: {message}")

    if violations:
        print("Dependency direction violations found:")
        for src, dst in sorted(set(violations)):
            print(f"- {src} -> {dst}")
        raise SystemExit(1)

    print("Dependency direction check passed.")


if __name__ == "__main__":
    main()
