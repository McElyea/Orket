from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.state_transition_registry import state_transition_registry_snapshot

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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export state transition registry as Mermaid.")
    parser.add_argument(
        "--out-mermaid",
        default="docs/generated/state_transition_registry.mmd",
        help="Mermaid output path.",
    )
    parser.add_argument(
        "--out-json",
        default="docs/generated/state_transition_registry_export.json",
        help="JSON summary output path.",
    )
    return parser.parse_args(argv)


def build_state_transition_mermaid(snapshot: dict[str, Any] | None = None) -> str:
    payload = snapshot or state_transition_registry_snapshot()
    lines: list[str] = ["flowchart LR"]
    for domain in payload.get("domains", []):
        if not isinstance(domain, dict):
            continue
        domain_name = str(domain.get("domain") or "").strip()
        if not domain_name:
            continue
        states = [str(token).strip() for token in domain.get("states", []) if str(token).strip()]
        transitions = [row for row in domain.get("transitions", []) if isinstance(row, dict)]
        lines.append(f'  subgraph {domain_name}["{domain_name}"]')
        for state in states:
            node = f"{domain_name}__{state}".replace("-", "_")
            lines.append(f'    {node}["{state}"]')
        lines.append("  end")
        for row in transitions:
            source = str(row.get("from") or "").strip()
            targets = [str(token).strip() for token in row.get("to", []) if str(token).strip()]
            source_node = f"{domain_name}__{source}".replace("-", "_")
            for target in targets:
                target_node = f"{domain_name}__{target}".replace("-", "_")
                lines.append(f"  {source_node} --> {target_node}")
    return "\n".join(lines) + "\n"


def export_state_transition_mermaid(
    *,
    out_mermaid: Path,
    out_json: Path | None,
) -> dict[str, Any]:
    snapshot = state_transition_registry_snapshot()
    mermaid = build_state_transition_mermaid(snapshot)
    out_mermaid.parent.mkdir(parents=True, exist_ok=True)
    out_mermaid.write_text(mermaid, encoding="utf-8")

    domains = [row for row in snapshot.get("domains", []) if isinstance(row, dict)]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "ok": True,
        "mermaid_path": str(out_mermaid),
        "domains_count": len(domains),
        "states_total": sum(len(list(row.get("states", []))) for row in domains),
        "transitions_total": sum(
            len(list(targets))
            for row in domains
            for transition in row.get("transitions", [])
            if isinstance(transition, dict)
            for targets in [transition.get("to", [])]
            if isinstance(targets, list)
        ),
    }
    if out_json is not None:
        write_payload_with_diff_ledger(out_json, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_mermaid = Path(args.out_mermaid).resolve()
    out_json = Path(args.out_json).resolve() if str(args.out_json or "").strip() else None
    payload = export_state_transition_mermaid(out_mermaid=out_mermaid, out_json=out_json)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
