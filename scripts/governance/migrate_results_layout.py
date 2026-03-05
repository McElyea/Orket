from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


RESULTS_ROOT = Path("benchmarks/results")
DOMAIN_DIRS = {
    "acceptance",
    "benchmarks",
    "ci",
    "context",
    "explorer",
    "extensions",
    "gitea",
    "governance",
    "nervous_system",
    "odr",
    "ops",
    "prompt_lab",
    "protocol",
    "providers",
    "quant",
    "replay",
    "reviewrun",
    "rulesim",
    "sdk",
    "security",
    "streaming",
    "tiering",
}


@dataclass(frozen=True)
class MovePlan:
    source: Path
    destination: Path
    reason: str


def _map_name(name: str, *, is_dir: bool) -> tuple[Path, str]:
    if is_dir:
        if name == "non_quant_live":
            return Path("streaming/non_quant_live"), "known_legacy_dir"
        if name == "live_1000_consistency_stress_runs":
            return Path("streaming/live_1000_consistency_stress_runs"), "known_legacy_dir"
        if name == "odr_calibration":
            return Path("odr/odr_calibration"), "known_legacy_dir"
        if name == "odr_vs_no_odr_with_odr":
            return Path("odr/odr_vs_no_odr_with_odr"), "known_legacy_dir"
        if name == "protocol_governed":
            return Path("protocol/protocol_governed"), "known_legacy_dir"
        if name == "quant_sweep":
            return Path("quant/quant_sweep"), "known_legacy_dir"
        if name == "quant_sweep_archive":
            return Path("quant/quant_sweep_archive"), "known_legacy_dir"
        if name == "script_reorg":
            return Path("governance/script_reorg"), "known_legacy_dir"
        return Path(f"benchmarks/{name}"), "fallback_dir"

    if name.startswith("ci_failure_dump"):
        return Path(f"ci/{name}"), "prefix_ci"
    if name.startswith("gitea_state"):
        return Path(f"gitea/{name}"), "prefix_gitea"
    if name.startswith("security_") or name.startswith("telemetry_artifact_fields"):
        return Path(f"security/{name}"), "prefix_security"
    if name.startswith(("retention_", "dependency_", "workitem_", "cli_regression_")):
        return Path(f"governance/{name}"), "prefix_governance"
    if name.startswith(("architecture_pilot_", "microservices_", "monolith_", "live_acceptance_")):
        return Path(f"acceptance/{name}"), "prefix_acceptance"
    if name.startswith(
        (
            "benchmark_",
            "live_card_",
            "live_rock_",
            "phase4_",
            "phase5_",
            "phase6_",
            "determinism_",
            "memory_",
            "offline_matrix_",
            "orchestration_",
        )
    ):
        return Path(f"benchmarks/{name}"), "prefix_benchmarks"
    if name.startswith(("live_1000_", "real_service_")):
        return Path(f"streaming/{name}"), "prefix_streaming"
    if name.startswith("odr_"):
        return Path(f"odr/{name}"), "prefix_odr"
    if name.startswith("nervous_system_"):
        return Path(f"nervous_system/{name}"), "prefix_nervous_system"
    if name.startswith("reviewrun_"):
        return Path(f"reviewrun/{name}"), "prefix_reviewrun"
    if name.startswith("prompt_"):
        return Path(f"prompt_lab/{name}"), "prefix_prompt_lab"
    if name.startswith("rulesim_"):
        return Path(f"rulesim/{name}"), "prefix_rulesim"
    if name.startswith("failure_modes"):
        return Path(f"replay/{name}"), "prefix_replay"
    return Path(f"benchmarks/{name}"), "fallback_file"


def _plan_moves(root: Path) -> list[MovePlan]:
    plans: list[MovePlan] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.name in DOMAIN_DIRS:
            continue
        rel, reason = _map_name(child.name, is_dir=child.is_dir())
        plans.append(MovePlan(source=child, destination=root / rel, reason=reason))
    return plans


def _resolve_collision(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return dest.with_name(f"{dest.name}.legacy_{stamp}")


def _execute_moves(plans: list[MovePlan]) -> list[dict[str, str]]:
    moved: list[dict[str, str]] = []
    for plan in plans:
        final_dest = _resolve_collision(plan.destination)
        final_dest.parent.mkdir(parents=True, exist_ok=True)
        plan.source.rename(final_dest)
        moved.append(
            {
                "source": str(plan.source).replace("\\", "/"),
                "destination": str(final_dest).replace("\\", "/"),
                "reason": plan.reason,
            }
        )
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Relayout benchmarks/results into domain-aligned folders.")
    parser.add_argument("--root", default=str(RESULTS_ROOT), help="Results root directory.")
    parser.add_argument("--execute", action="store_true", help="Perform moves (default is dry-run).")
    parser.add_argument(
        "--out",
        default="benchmarks/results/governance/results_layout_migration.json",
        help="JSON report output path.",
    )
    args = parser.parse_args()

    root = Path(str(args.root)).resolve()
    if not root.exists():
        raise SystemExit(f"Results root not found: {root}")

    plans = _plan_moves(root)
    moved: list[dict[str, str]] = []
    if args.execute:
        moved = _execute_moves(plans)

    report = {
        "schema_version": "results_layout_migration_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "root": str(root).replace("\\", "/"),
        "execute": bool(args.execute),
        "planned_moves": [
            {
                "source": str(p.source).replace("\\", "/"),
                "destination": str(p.destination).replace("\\", "/"),
                "reason": p.reason,
            }
            for p in plans
        ],
        "moved": moved,
        "planned_count": len(plans),
        "moved_count": len(moved),
    }

    out = Path(str(args.out)).resolve()
    write_payload_with_diff_ledger(out, report)
    print(json.dumps({"planned_count": len(plans), "moved_count": len(moved), "execute": bool(args.execute)}, indent=2))
    print(f"report={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
