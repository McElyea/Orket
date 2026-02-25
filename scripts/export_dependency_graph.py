from __future__ import annotations

import ast
import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from dependency_policy import POLICY_PATH, PROJECT_ROOT, load_dependency_policy

OUTPUT_DIR = PROJECT_ROOT / "docs" / "architecture"
OUTPUT_JSON = OUTPUT_DIR / "dependency_graph_snapshot.json"
OUTPUT_MD = OUTPUT_DIR / "dependency_graph_snapshot.md"


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


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _build_snapshot() -> Dict[str, object]:
    policy = load_dependency_policy()
    modules: Dict[str, Dict[str, object]] = {}
    layer_edges: Counter[Tuple[str, str]] = Counter()
    module_edges: Counter[Tuple[str, str]] = Counter()
    unknown_modules: set[str] = set()
    scanned_files = 0

    scanned_roots = [PROJECT_ROOT / root for root in policy.scan_roots]
    for root in scanned_roots:
        if not root.exists():
            raise ValueError(f"Dependency policy scan root missing: {root}")
        if not any(root.rglob("*.py")):
            raise ValueError(f"Dependency policy scan root has no python files: {root}")

    for root in scanned_roots:
        for py in _iter_py_files(root):
            scanned_files += 1
            src_module = _module_from_path(py)
            try:
                src_layer = policy.layer_for_module(src_module)
            except ValueError:
                unknown_modules.add(src_module)
                continue
            imports = _imports_for_file(py)
            local_imports = [m for m in imports if m.startswith("orket.")]
            modules[src_module] = {
                "path": str(py.relative_to(PROJECT_ROOT)),
                "layer": src_layer,
                "imports": sorted(set(local_imports)),
            }
            for dst in local_imports:
                try:
                    dst_layer = policy.layer_for_module(dst)
                except ValueError:
                    unknown_modules.add(dst)
                    continue
                module_edges[(src_module, dst)] += 1
                layer_edges[(src_layer, dst_layer)] += 1

    if unknown_modules:
        unknown_list = ", ".join(sorted(unknown_modules))
        raise ValueError(f"Unknown module classification(s): {unknown_list}")

    forbidden_edge_hits = [
        {"source_layer": src, "target_layer": dst, "count": count}
        for (src, dst), count in sorted(layer_edges.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
        if (src, dst) in policy.forbidden_edges
    ]
    legacy_edge_count = sum(
        count for (src, dst), count in layer_edges.items() if src == "legacy" or dst == "legacy"
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "module_count": len(modules),
        "scan": {
            "files_scanned": scanned_files,
            "roots": [str(root.relative_to(PROJECT_ROOT)) for root in scanned_roots],
        },
        "policy": {
            "path": str(POLICY_PATH.relative_to(PROJECT_ROOT)),
            "policy_id": policy.policy_id,
            "schema_version": policy.schema_version,
            "forbidden_edges": [
                {"source_layer": src, "target_layer": dst}
                for src, dst in sorted(policy.forbidden_edges)
            ],
        },
        "modules": modules,
        "layer_edges": [
            {"source_layer": s, "target_layer": d, "count": c}
            for (s, d), c in sorted(layer_edges.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
        ],
        "forbidden_edge_hits": forbidden_edge_hits,
        "legacy_edge_budget": {
            "actual_edges": legacy_edge_count,
            "max_edges": policy.legacy_edge_budget_max,
            "exceeded": (
                policy.legacy_edge_budget_max is not None and legacy_edge_count > policy.legacy_edge_budget_max
            ),
        },
        "top_module_edges": [
            {"source_module": s, "target_module": d, "count": c}
            for (s, d), c in module_edges.most_common(100)
        ],
    }


def _to_markdown(snapshot: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append("# Dependency Graph Snapshot")
    lines.append("")
    lines.append(f"Generated: `{snapshot['generated_at']}`")
    lines.append(f"Module count: `{snapshot['module_count']}`")
    lines.append(f"Files scanned: `{snapshot['scan']['files_scanned']}`")
    lines.append(f"Policy: `{snapshot['policy']['path']}` (`{snapshot['policy']['schema_version']}`)")
    lines.append("")
    lines.append("## Layer Edges")
    lines.append("")
    lines.append("| Source | Target | Count |")
    lines.append("|---|---|---:|")
    for edge in snapshot["layer_edges"]:
        lines.append(f"| `{edge['source_layer']}` | `{edge['target_layer']}` | {edge['count']} |")
    lines.append("")
    lines.append("## Forbidden Edge Hits")
    lines.append("")
    lines.append("| Source | Target | Count |")
    lines.append("|---|---|---:|")
    for edge in snapshot["forbidden_edge_hits"]:
        lines.append(f"| `{edge['source_layer']}` | `{edge['target_layer']}` | {edge['count']} |")
    if not snapshot["forbidden_edge_hits"]:
        lines.append("| _none_ | _none_ | 0 |")
    lines.append("")
    lines.append("## Legacy Edge Budget")
    lines.append("")
    lines.append(
        f"- Actual legacy edges: `{snapshot['legacy_edge_budget']['actual_edges']}`"
    )
    lines.append(
        f"- Budget max: `{snapshot['legacy_edge_budget']['max_edges']}`"
    )
    lines.append(
        f"- Exceeded: `{snapshot['legacy_edge_budget']['exceeded']}`"
    )
    lines.append("")
    lines.append("## Top Module Edges (Top 50)")
    lines.append("")
    lines.append("| Source Module | Target Module | Count |")
    lines.append("|---|---|---:|")
    for edge in snapshot["top_module_edges"][:50]:
        lines.append(f"| `{edge['source_module']}` | `{edge['target_module']}` | {edge['count']} |")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This is a structural import snapshot; it is not a runtime call graph.")
    lines.append("- Use with architecture boundary tests to enforce dependency direction.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export dependency graph snapshot.")
    parser.add_argument("--out-json", type=Path, default=OUTPUT_JSON, help="Output JSON snapshot path.")
    parser.add_argument("--out-md", type=Path, default=OUTPUT_MD, help="Output markdown snapshot path.")
    args = parser.parse_args()

    out_json = args.out_json.resolve()
    out_md = args.out_md.resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    out_json.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    out_md.write_text(_to_markdown(snapshot), encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
