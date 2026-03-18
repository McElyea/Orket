from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.probes.probe_support import now_utc_iso, observability_inventory, run_summary, write_report

DEFAULT_SESSION_ID = "probe-p03-epic-trace"
DEFAULT_OUTPUT = "benchmarks/results/probes/p04_odr_cards_integration.json"
ODR_SIGNALS = (
    "history_rounds",
    "stop_reason",
    "CODE_LEAK",
    "STABLE_DIFF_FLOOR",
    "LOOP_DETECTED",
    "FORMAT_VIOLATION",
)
CODE_PATTERNS = (
    "run_round(",
    "ReactorConfig",
    "ReactorState",
    "orket.kernel.v1.odr",
    "history_rounds",
    "CODE_LEAK",
)
CODE_SCAN_ROOTS = (
    REPO_ROOT / "orket" / "application",
    REPO_ROOT / "orket" / "runtime",
    REPO_ROOT / "orket" / "orchestration",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 1 probe P-04: ODR/cards integration audit.")
    parser.add_argument("--workspace", default=".probe_workspace_p03")
    parser.add_argument("--session-id", default=DEFAULT_SESSION_ID)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _scan_observability(workspace: Path, session_id: str) -> dict[str, Any]:
    inventory = observability_inventory(workspace, session_id)
    run_summary_payload = run_summary(workspace, session_id)
    scan_targets = [workspace / item["path"] for item in inventory]
    summary_path = workspace / "runs" / session_id / "run_summary.json"
    if summary_path.exists():
        scan_targets.append(summary_path)

    hits: list[dict[str, Any]] = []
    for path in scan_targets:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        matched = [signal for signal in ODR_SIGNALS if signal in text]
        if not matched:
            continue
        hits.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "signals": matched,
            }
        )

    return {
        "inventory_count": len(inventory),
        "hits": hits,
        "run_summary_present": bool(run_summary_payload),
        "run_summary_has_stop_reason": "stop_reason" in run_summary_payload,
    }


def _scan_codebase() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for root in CODE_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            matched_rows: list[dict[str, Any]] = []
            for line_number, line in enumerate(lines, start=1):
                matched = [pattern for pattern in CODE_PATTERNS if pattern in line]
                if not matched:
                    continue
                matched_rows.append(
                    {
                        "line": line_number,
                        "patterns": matched,
                        "text": line.strip(),
                    }
                )
            if matched_rows:
                hits.append(
                    {
                        "path": path.relative_to(REPO_ROOT).as_posix(),
                        "matches": matched_rows,
                    }
                )
    integration_hits = [row for row in hits if row["path"].startswith(("orket/application/", "orket/runtime/", "orket/orchestration/"))]
    return {
        "hits": hits,
        "integration_hits": integration_hits,
    }


def _conclusion(observability_scan: dict[str, Any], code_scan: dict[str, Any]) -> dict[str, Any]:
    artifact_hits = list(observability_scan.get("hits") or [])
    integration_hits = list(code_scan.get("integration_hits") or [])
    if artifact_hits:
        return {
            "integration_status": "artifacts_present",
            "summary": "ODR fingerprints were found in cards-engine artifacts.",
        }
    if integration_hits:
        return {
            "integration_status": "code_path_detected_no_artifacts",
            "summary": "Cards-engine code references ODR symbols, but the scanned run did not emit ODR artifacts.",
        }
    return {
        "integration_status": "independent_subsystems",
        "summary": "No ODR artifact fingerprints or cards-path code references were found.",
    }


def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(str(args.workspace)).resolve()
    observability_scan = _scan_observability(workspace, str(args.session_id))
    code_scan = _scan_codebase()
    conclusion = _conclusion(observability_scan, code_scan)
    observed_path = "primary" if observability_scan.get("inventory_count") else "fallback"
    return {
        "schema_version": "phase1_probe.p04.v1",
        "recorded_at_utc": now_utc_iso(),
        "probe_id": "P-04",
        "probe_status": "observed",
        "proof_kind": "structural",
        "observed_path": observed_path,
        "observed_result": "success",
        "workspace": str(workspace),
        "session_id": str(args.session_id),
        "odr_signals": list(ODR_SIGNALS),
        "observability_scan": observability_scan,
        "code_scan": code_scan,
        "conclusion": conclusion,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    payload = _run_probe(args)
    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        conclusion = persisted.get("conclusion") if isinstance(persisted.get("conclusion"), dict) else {}
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"integration_status={conclusion.get('integration_status', '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
