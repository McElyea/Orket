from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "orket"
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


def _layer_for_module(module: str) -> str:
    if not module.startswith("orket."):
        return "external"
    parts = module.split(".")
    if len(parts) < 2:
        return "root"
    top = parts[1]
    if top in {"core", "application", "adapters", "interfaces", "platform"}:
        return top
    if top in {"domain", "infrastructure", "services", "orchestration", "decision_nodes", "runtime", "agents", "vendors"}:
        return top
    return "root"


def _iter_py_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _build_snapshot() -> Dict[str, object]:
    modules: Dict[str, Dict[str, object]] = {}
    layer_edges: Counter[Tuple[str, str]] = Counter()
    module_edges: Counter[Tuple[str, str]] = Counter()

    for py in _iter_py_files(PACKAGE_ROOT):
        src_module = _module_from_path(py)
        src_layer = _layer_for_module(src_module)
        imports = _imports_for_file(py)
        local_imports = [m for m in imports if m.startswith("orket.")]
        modules[src_module] = {
            "path": str(py.relative_to(PROJECT_ROOT)),
            "layer": src_layer,
            "imports": sorted(set(local_imports)),
        }
        for dst in local_imports:
            dst_layer = _layer_for_module(dst)
            module_edges[(src_module, dst)] += 1
            layer_edges[(src_layer, dst_layer)] += 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "module_count": len(modules),
        "modules": modules,
        "layer_edges": [
            {"source_layer": s, "target_layer": d, "count": c}
            for (s, d), c in sorted(layer_edges.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
        ],
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
    lines.append("")
    lines.append("## Layer Edges")
    lines.append("")
    lines.append("| Source | Target | Count |")
    lines.append("|---|---|---:|")
    for edge in snapshot["layer_edges"]:
        lines.append(f"| `{edge['source_layer']}` | `{edge['target_layer']}` | {edge['count']} |")
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    OUTPUT_JSON.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(_to_markdown(snapshot), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")


if __name__ == "__main__":
    main()
