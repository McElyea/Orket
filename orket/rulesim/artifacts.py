from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .canonical import canonical_json


def _ulid_like() -> str:
    millis = int(time.time() * 1000)
    entropy = uuid4().hex[:16]
    return f"{millis:013d}{entropy}".upper()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic_text(path, canonical_json(payload) + "\n")


def _write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}-{uuid4().hex[:8]}")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(row))
            handle.write("\n")


def _write_episodes_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "episode_id,terminal_reason,steps,has_anomaly\n"
    lines = [header]
    for row in rows:
        lines.append(
            f"{row['episode_id']},{row['terminal_reason']},{row['steps']},{'1' if row['has_anomaly'] else '0'}\n"
        )
    _write_atomic_text(path, "".join(lines))


def write_checkpoint_episode(*, checkpoint_root: Path, episode_payload: dict[str, Any]) -> None:
    episode_id = str(episode_payload.get("episode_id") or "").strip()
    if not episode_id:
        raise ValueError("episode_payload.episode_id is required")
    path = checkpoint_root / f"{episode_id}.json"
    _write_json(path, episode_payload)


def write_artifact_bundle(
    *,
    workspace: Path,
    run_config_payload: dict[str, Any],
    summary_payload: dict[str, Any],
    episode_payloads: list[dict[str, Any]],
    suspicious_rows: list[dict[str, Any]],
    probe_payloads: dict[str, dict[str, Any]],
    artifact_policy: str,
) -> dict[str, str]:
    run_id = _ulid_like()
    root = workspace / "rulesim" / "run" / run_id
    run_payload_for_digest = dict(run_config_payload)
    run_payload_for_digest.pop("run_id", None)
    run_digest = hashlib.sha256(canonical_json(run_payload_for_digest).encode("utf-8")).hexdigest()
    summary_digest = hashlib.sha256(canonical_json(summary_payload).encode("utf-8")).hexdigest()
    run_json = dict(run_config_payload)
    run_json["run_id"] = run_id
    run_json["run_digest"] = run_digest
    _write_json(root / "run.json", run_json)
    _write_json(root / "summary.json", summary_payload)

    suspicious_index = {"episodes": suspicious_rows}
    _write_json(root / "suspicious" / "index.json", suspicious_index)
    if artifact_policy in {"all", "suspicious_only"}:
        suspicious_ids = {str(row.get("episode_id") or "") for row in suspicious_rows}
        for row in episode_payloads:
            episode_id = str(row["episode_id"])
            write_trace = artifact_policy == "all" or episode_id in suspicious_ids
            episode_root = root / "episodes" / episode_id
            _write_json(episode_root / "episode.json", row["episode"])
            if write_trace:
                _write_jsonl(episode_root / "trace.jsonl", row["trace"])

    for probe_id, payload in probe_payloads.items():
        probe_root = root / "probes" / probe_id
        _write_json(probe_root / "summary.json", payload["summary"])
        _write_episodes_csv(probe_root / "episodes.csv", payload["episodes_csv"])
    return {
        "run_id": run_id,
        "run_digest": run_digest,
        "summary_digest": summary_digest,
        "artifact_root": str(root),
        "artifact_root_posix": str(Path(os.path.normpath(root)).as_posix()),
    }
