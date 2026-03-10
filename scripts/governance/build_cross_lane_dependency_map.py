from __future__ import annotations

import argparse
import json
import re
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


_ROADMAP_PLAN_PTR = re.compile(r"^\s*\d+\.\s*(?P<label>.+?)\s*--.*?`(?P<plan>docs/[^`]+)`")
_BACKTICK_PATH = re.compile(r"`(docs/[^`]+)`")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build cross-lane dependency map from roadmap plan pointers.")
    parser.add_argument("--workspace", default=".", help="Workspace root containing docs/ROADMAP.md.")
    parser.add_argument(
        "--out-json",
        default="docs/generated/cross_lane_dependency_map.json",
        help="JSON output path.",
    )
    parser.add_argument(
        "--out-mermaid",
        default="docs/generated/cross_lane_dependency_map.mmd",
        help="Mermaid output path.",
    )
    return parser.parse_args(argv)


def _extract_lane_plan_pointers(roadmap_text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in roadmap_text.splitlines():
        match = _ROADMAP_PLAN_PTR.match(line)
        if not match:
            continue
        label = str(match.group("label") or "").strip()
        plan_path = str(match.group("plan") or "").strip()
        if label and plan_path:
            rows.append((label, plan_path))
    return rows


def _extract_dependencies(plan_text: str, plan_path: str) -> list[str]:
    dependencies = {
        str(path).strip()
        for path in _BACKTICK_PATH.findall(plan_text)
        if str(path).strip() and str(path).strip() != plan_path
    }
    return sorted(dependencies)


def build_cross_lane_dependency_map(*, workspace: Path) -> dict[str, Any]:
    roadmap_path = workspace / "docs" / "ROADMAP.md"
    if not roadmap_path.exists():
        raise ValueError(f"E_CROSS_LANE_DEPENDENCY_MAP_ROADMAP_MISSING:{roadmap_path}")
    roadmap_text = roadmap_path.read_text(encoding="utf-8")
    plan_pointers = _extract_lane_plan_pointers(roadmap_text)

    lanes: list[dict[str, Any]] = []
    missing_plan_paths: list[str] = []
    for lane_label, plan_rel_path in plan_pointers:
        plan_path = workspace / Path(plan_rel_path)
        if not plan_path.exists():
            missing_plan_paths.append(plan_rel_path)
            dependencies: list[str] = []
        else:
            plan_text = plan_path.read_text(encoding="utf-8")
            dependencies = _extract_dependencies(plan_text, plan_rel_path)
        lanes.append(
            {
                "lane": lane_label,
                "plan_path": plan_rel_path,
                "dependencies": dependencies,
            }
        )

    edges = [
        {"lane": row["lane"], "plan_path": row["plan_path"], "dependency": dependency}
        for row in lanes
        for dependency in row["dependencies"]
    ]
    return {
        "schema_version": "1.0",
        "ok": not missing_plan_paths,
        "roadmap_path": "docs/ROADMAP.md",
        "lane_count": len(lanes),
        "edge_count": len(edges),
        "missing_plan_paths": missing_plan_paths,
        "lanes": lanes,
        "edges": edges,
    }


def build_cross_lane_dependency_mermaid(payload: dict[str, Any]) -> str:
    lines: list[str] = ["graph LR"]
    for index, lane in enumerate(payload.get("lanes", [])):
        if not isinstance(lane, dict):
            continue
        lane_node = f"lane_{index}"
        lane_label = str(lane.get("lane") or "").strip()
        lines.append(f'  {lane_node}["{lane_label}"]')
        dependencies = [str(dep).strip() for dep in lane.get("dependencies", []) if str(dep).strip()]
        for dep_index, dependency in enumerate(dependencies):
            dep_node = f"dep_{index}_{dep_index}"
            lines.append(f'  {dep_node}["{dependency}"]')
            lines.append(f"  {lane_node} --> {dep_node}")
    return "\n".join(lines) + "\n"


def export_cross_lane_dependency_map(
    *,
    workspace: Path,
    out_json: Path,
    out_mermaid: Path,
) -> dict[str, Any]:
    payload = build_cross_lane_dependency_map(workspace=workspace)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_mermaid.parent.mkdir(parents=True, exist_ok=True)
    write_payload_with_diff_ledger(out_json, payload)
    out_mermaid.write_text(build_cross_lane_dependency_mermaid(payload), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    workspace = Path(args.workspace).resolve()
    payload = export_cross_lane_dependency_map(
        workspace=workspace,
        out_json=(workspace / Path(args.out_json)).resolve(),
        out_mermaid=(workspace / Path(args.out_mermaid)).resolve(),
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
