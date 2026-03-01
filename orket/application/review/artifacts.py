from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from orket.application.review.models import (
    DeterministicReviewDecisionPayload,
    ModelAssistedCritiquePayload,
    ReviewRunManifest,
    ReviewSnapshot,
    ResolvedPolicy,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_review_run_bundle(
    *,
    artifact_dir: Path,
    snapshot: ReviewSnapshot,
    resolved_policy: ResolvedPolicy,
    deterministic: DeterministicReviewDecisionPayload,
    manifest: ReviewRunManifest,
    model_assisted: Optional[ModelAssistedCritiquePayload] = None,
) -> Dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = artifact_dir / "snapshot.json"
    policy_path = artifact_dir / "policy_resolved.json"
    deterministic_path = artifact_dir / "deterministic_decision.json"
    manifest_path = artifact_dir / "run_manifest.json"
    replay_path = artifact_dir / "replay_instructions.txt"
    model_path = artifact_dir / "model_assisted_critique.json"

    _write_json(snapshot_path, snapshot.to_dict())
    _write_json(policy_path, resolved_policy.to_dict())
    _write_json(deterministic_path, deterministic.to_dict())
    _write_json(manifest_path, manifest.to_dict())
    if model_assisted is not None:
        _write_json(model_path, model_assisted.to_dict())

    replay_lines = [
        "Replay this run offline (no remote fetch):",
        f"orket review replay --run-dir {artifact_dir}",
        "",
        "or explicitly:",
        f"orket review replay --snapshot {snapshot_path} --policy {policy_path}",
    ]
    replay_path.write_text("\n".join(replay_lines) + "\n", encoding="utf-8")

    return {
        "snapshot": str(snapshot_path),
        "policy_resolved": str(policy_path),
        "deterministic_decision": str(deterministic_path),
        "model_assisted_critique": str(model_path) if model_assisted is not None else "",
        "run_manifest": str(manifest_path),
        "replay_instructions": str(replay_path),
    }

