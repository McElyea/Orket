from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.runtime.protocol_replay import ProtocolReplayEngine


def resolve_run_ids(*, runs_root: Path, run_ids: list[str]) -> list[str]:
    explicit = [str(run_id).strip() for run_id in run_ids if str(run_id).strip()]
    if explicit:
        return sorted(set(explicit))
    discovered = [
        path.name
        for path in sorted(runs_root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (path / "events.log").exists()
    ]
    return discovered


def resolve_run_dir(*, runs_root: Path, run_id: str) -> Path:
    candidate = (runs_root / str(run_id).strip()).resolve()
    if not candidate.is_relative_to(runs_root):
        raise ValueError(f"invalid run id: {run_id}")
    return candidate


def compare_protocol_determinism_campaign(
    *,
    runs_root: Path,
    run_ids: list[str],
    baseline_run_id: str | None = None,
) -> dict[str, Any]:
    candidates = resolve_run_ids(runs_root=runs_root, run_ids=run_ids)
    if not candidates:
        raise ValueError("No run ids found with events.log under runs root.")

    baseline = str(baseline_run_id or "").strip() or candidates[0]
    if baseline not in candidates:
        candidates.append(baseline)
        candidates = sorted(set(candidates))

    baseline_dir = resolve_run_dir(runs_root=runs_root, run_id=baseline)
    baseline_events = baseline_dir / "events.log"
    if not baseline_events.exists():
        raise ValueError(f"Baseline events.log not found: {baseline_events}")

    engine = ProtocolReplayEngine()
    comparisons: list[dict[str, Any]] = []
    mismatch_count = 0
    for run_id in candidates:
        candidate_dir = resolve_run_dir(runs_root=runs_root, run_id=run_id)
        events_path = candidate_dir / "events.log"
        if not events_path.exists():
            comparisons.append(
                {
                    "run_id": run_id,
                    "status": "missing_events",
                    "events_path": str(events_path),
                }
            )
            mismatch_count += 1
            continue

        comparison = engine.compare_replays(
            run_a_events_path=baseline_events,
            run_b_events_path=events_path,
            run_a_artifact_root=(baseline_dir / "artifacts") if (baseline_dir / "artifacts").exists() else None,
            run_b_artifact_root=(candidate_dir / "artifacts") if (candidate_dir / "artifacts").exists() else None,
        )
        deterministic_match = bool(comparison.get("deterministic_match", False))
        if run_id == baseline:
            deterministic_match = True
        if not deterministic_match:
            mismatch_count += 1
        comparisons.append(
            {
                "run_id": run_id,
                "status": "ok",
                "deterministic_match": deterministic_match,
                "difference_count": len(comparison.get("differences") or []),
                "state_digest_a": comparison.get("state_digest_a"),
                "state_digest_b": comparison.get("state_digest_b"),
                "differences": comparison.get("differences") or [],
            }
        )

    return {
        "runs_root": str(runs_root),
        "baseline_run_id": baseline,
        "candidate_count": len(candidates),
        "mismatch_count": mismatch_count,
        "all_match": mismatch_count == 0,
        "comparisons": comparisons,
    }
