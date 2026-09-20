"""Export observed dependencies and their separate policy verdict."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.governance.dependency_policy import POLICY_PATH, PROJECT_ROOT
from scripts.governance.dependency_report import build_dependency_report, report_summary

OUTPUT_JSON = PROJECT_ROOT / "docs/architecture/dependency_graph_snapshot.json"
OUTPUT_MD = PROJECT_ROOT / "docs/architecture/dependency_graph_snapshot.md"


def build_dependency_snapshot(*, root: Path = PROJECT_ROOT, policy_path: Path = POLICY_PATH) -> dict:
    return build_dependency_report(root=root, policy_path=policy_path)


def _dynamic_routes_markdown(snapshot: dict) -> list[str]:
    routes = snapshot["observed"].get("resolved_dynamic_routes", [])
    lines = ["", "## Bounded dynamic routes", "",
             "These routes have an inspected syntactic proof; they are not analysis-error waivers.", "",
             "| Source | Line | Kind | Proven boundary |", "|---|---:|---|---|"]
    for row in routes:
        boundary = (f"`{row['target']}` via `{row['factory']}`" if row["kind"] == "importer_interception"
                    else f"Plain absolute name outside `{row['excluded_namespace']}` via `{row['validator']}`")
        lines.append(f"| `{row['path']}` | {row['line']} | `{row['kind']}` | {boundary} |")
    if not routes:
        lines.append("| none | | | |")
    return lines


def _to_markdown(snapshot: dict) -> str:
    summary = report_summary(snapshot)
    lines = [
        "# Dependency Graph Snapshot",
        "",
        f"Generated: `{snapshot['generated_at']}`",
        "",
        "Generated from the canonical dependency policy; do not edit this view by hand.",
        "This is conservative static import evidence, not a runtime call graph or a core-purity proof.",
        "",
        f"Collection: `{summary['collection_ok']}`. Policy verdict: `{summary['ok']}`.",
        f"Files: {summary['files']}; import sites: {summary['edges']}; forbidden pairs: {summary['violations']}; "
        f"analysis errors: {summary['analysis_errors']}; authority cycles: {summary['authority_cycles']}.",
        "",
    ]
    contract = snapshot["policy"].get("contract", {})
    lines += ["## Module classification", "", "| Prefix | Layer |", "|---|---|"]
    lines += [f"| `{name}` | `{layer}` |" for name, layer in contract.get("classifications", {}).items()]
    lines += ["", "## Allowed layer edges", "", "| Source | Target |", "|---|---|"]
    lines += [f"| `{left}` | `{right}` |" for left, right in contract.get("allowed_edges", [])]
    lines += [
        "",
        "Decision-node core targets: " + ", ".join(f"`{n}`" for n in contract.get("decision_core_contracts", [])),
        "",
        "Side-effect-free adapter targets: "
        + (", ".join(f"`{n}`" for n in contract.get("side_effect_free_adapters", [])) or "none declared"),
        "",
        "## Observed layer edges",
        "",
        "| Source | Target | Import sites |",
        "|---|---|---:|",
    ]
    lines += [
        f"| `{row['source']}` | `{row['target']}` | {row['count']} |"
        for row in snapshot["observed"].get("layer_edges", [])
    ]
    lines += _dynamic_routes_markdown(snapshot)
    exceptions = snapshot["verdict"].get("exceptions", {})
    lines += [
        "",
        "## Exceptions",
        "",
        f"Consumed: {len(exceptions.get('consumed', []))}; "
        f"unused: {len(exceptions.get('unused', []))}; redundant: {len(exceptions.get('redundant', []))}.",
        "",
        "Exact exception metadata, all import sites, source hashes, analysis errors and authority cycles are in the JSON snapshot.",
        "An exported graph does not establish a passing verdict. Unresolved routes and forbidden edges remain failures.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--out-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUTPUT_MD)
    args = parser.parse_args()
    report = build_dependency_snapshot(root=args.root.resolve(), policy_path=args.policy.resolve())
    write_payload_with_diff_ledger(args.out_json.resolve(), report)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(_to_markdown(report), encoding="utf-8")
    print(json.dumps(report_summary(report), sort_keys=True))
    # An export can complete with a failing policy verdict; collection errors still fail.
    return 0 if report["collection_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
