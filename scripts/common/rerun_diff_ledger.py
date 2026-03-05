from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_object(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _payload_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _sample_path(path: str, samples: list[str], max_sample_paths: int) -> None:
    if len(samples) >= max_sample_paths:
        return
    if path in samples:
        return
    samples.append(path)


def _path_for_child(parent: str, child: str) -> str:
    if parent == "$":
        return f"$.{child}"
    return f"{parent}.{child}"


def _path_for_index(parent: str, index: int) -> str:
    return f"{parent}[{index}]"


def _count_paths(value: Any) -> int:
    if isinstance(value, dict):
        count = len(value)
        for child in value.values():
            count += _count_paths(child)
        return count
    if isinstance(value, list):
        count = len(value)
        for child in value:
            count += _count_paths(child)
        return count
    return 1


def _walk_diff(
    previous: Any,
    current: Any,
    *,
    path: str,
    diff_counts: dict[str, int],
    samples: list[str],
    max_sample_paths: int,
) -> None:
    if type(previous) is not type(current):
        diff_counts["changed_paths"] += 1
        _sample_path(path, samples, max_sample_paths)
        return

    if isinstance(previous, dict):
        previous_keys = set(previous.keys())
        current_keys = set(current.keys())
        for key in sorted(previous_keys - current_keys):
            diff_counts["removed_paths"] += 1
            _sample_path(_path_for_child(path, key), samples, max_sample_paths)
        for key in sorted(current_keys - previous_keys):
            diff_counts["added_paths"] += 1
            _sample_path(_path_for_child(path, key), samples, max_sample_paths)
        for key in sorted(previous_keys & current_keys):
            _walk_diff(
                previous[key],
                current[key],
                path=_path_for_child(path, key),
                diff_counts=diff_counts,
                samples=samples,
                max_sample_paths=max_sample_paths,
            )
        return

    if isinstance(previous, list):
        overlap = min(len(previous), len(current))
        if len(previous) > overlap:
            diff_counts["removed_paths"] += len(previous) - overlap
        if len(current) > overlap:
            diff_counts["added_paths"] += len(current) - overlap

        for index in range(overlap):
            _walk_diff(
                previous[index],
                current[index],
                path=_path_for_index(path, index),
                diff_counts=diff_counts,
                samples=samples,
                max_sample_paths=max_sample_paths,
            )
        if len(previous) != len(current):
            _sample_path(path, samples, max_sample_paths)
        return

    if previous != current:
        diff_counts["changed_paths"] += 1
        _sample_path(path, samples, max_sample_paths)


def _build_diff_summary(
    previous_payload: dict[str, Any] | None,
    current_payload: dict[str, Any],
    *,
    max_sample_paths: int,
) -> dict[str, Any]:
    if previous_payload is None:
        total_current = _count_paths(current_payload)
        return {
            "initial_write": True,
            "added_paths": 0,
            "removed_paths": 0,
            "changed_paths": 0,
            "paths_total_previous": 0,
            "paths_total_current": total_current,
            "paths_total_reference": total_current,
            "churn_paths": total_current,
            "churn_ratio": 1.0,
            "sample_paths": [],
        }

    diff_counts = {"added_paths": 0, "removed_paths": 0, "changed_paths": 0}
    samples: list[str] = []
    _walk_diff(
        previous_payload,
        current_payload,
        path="$",
        diff_counts=diff_counts,
        samples=samples,
        max_sample_paths=max(1, int(max_sample_paths)),
    )
    total_previous = _count_paths(previous_payload)
    total_current = _count_paths(current_payload)
    total_reference = max(1, total_previous, total_current)
    churn_paths = diff_counts["added_paths"] + diff_counts["removed_paths"] + diff_counts["changed_paths"]

    diff_counts["initial_write"] = False
    diff_counts["paths_total_previous"] = total_previous
    diff_counts["paths_total_current"] = total_current
    diff_counts["paths_total_reference"] = total_reference
    diff_counts["churn_paths"] = churn_paths
    diff_counts["churn_ratio"] = round(min(1.0, float(churn_paths) / float(total_reference)), 6)
    diff_counts["sample_paths"] = samples
    return diff_counts


def _resolve_major_diff_threshold(
    *,
    major_diff_threshold: float | None,
    paths_total_reference: int,
    small_payload_path_cutoff: int,
    medium_payload_path_cutoff: int,
    small_payload_threshold: float,
    medium_payload_threshold: float,
    large_payload_threshold: float,
) -> float | None:
    if major_diff_threshold is not None:
        return float(major_diff_threshold)

    path_count = max(1, int(paths_total_reference))
    if path_count <= max(1, int(small_payload_path_cutoff)):
        return float(small_payload_threshold)
    if path_count <= max(1, int(medium_payload_path_cutoff)):
        return float(medium_payload_threshold)
    return float(large_payload_threshold)


def append_payload_history(path: Path, payload: dict[str, Any], *, history_key: str = "history") -> dict[str, Any]:
    existing = _load_json_object(path)
    raw_history = existing.get(history_key) if isinstance(existing.get(history_key), list) else []
    history = [row for row in raw_history if isinstance(row, dict)]
    history.append(payload)
    envelope = {history_key: history}
    _write_json_object(path, envelope)
    return envelope


def write_payload_with_diff_ledger(
    path: Path,
    payload: dict[str, Any],
    *,
    ledger_key: str = "diff_ledger",
    max_entries: int = 30,
    max_sample_paths: int = 20,
    major_diff_threshold: float | None = None,
    major_diff_min_paths: int = 20,
    small_payload_path_cutoff: int = 250,
    medium_payload_path_cutoff: int = 1200,
    small_payload_threshold: float = 0.93,
    medium_payload_threshold: float = 0.88,
    large_payload_threshold: float = 0.8,
    major_diff_rollover_label: str = "major_diff",
) -> dict[str, Any]:
    existing = _load_json_object(path)
    existing_ledger_raw = existing.get(ledger_key) if isinstance(existing.get(ledger_key), list) else []
    existing_ledger = [row for row in existing_ledger_raw if isinstance(row, dict)]

    previous_payload: dict[str, Any] | None = None
    if existing:
        previous_payload = dict(existing)
        previous_payload.pop(ledger_key, None)

    before_digest = _payload_digest(previous_payload) if previous_payload is not None else None
    after_digest = _payload_digest(payload)
    changed = before_digest != after_digest
    diff = _build_diff_summary(previous_payload, payload, max_sample_paths=max_sample_paths)

    major_rollover: dict[str, Any] | None = None
    threshold = _resolve_major_diff_threshold(
        major_diff_threshold=major_diff_threshold,
        paths_total_reference=int(diff.get("paths_total_reference", 0) or 0),
        small_payload_path_cutoff=small_payload_path_cutoff,
        medium_payload_path_cutoff=medium_payload_path_cutoff,
        small_payload_threshold=small_payload_threshold,
        medium_payload_threshold=medium_payload_threshold,
        large_payload_threshold=large_payload_threshold,
    )
    churn_paths = int(diff.get("churn_paths", 0) or 0)
    min_paths = max(0, int(major_diff_min_paths))
    if (
        previous_payload is not None
        and changed
        and threshold is not None
        and threshold >= 0.0
        and churn_paths >= min_paths
        and float(diff.get("churn_ratio", 0.0) or 0.0) >= threshold
    ):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        suffix = major_diff_rollover_label.strip() or "major_diff"
        archive_name = f"{path.stem}.{suffix}_{stamp}{path.suffix}"
        archive_path = path.with_name(archive_name)
        _write_json_object(archive_path, existing)
        major_rollover = {
            "enabled": True,
            "threshold": threshold,
            "min_paths": min_paths,
            "churn_paths": churn_paths,
            "archive_path": str(archive_path).replace("\\", "/"),
        }

    entry = {
        "run_at_utc": _now_utc_iso(),
        "changed": changed,
        "before_digest": before_digest,
        "after_digest": after_digest,
        "diff": diff,
    }
    if major_rollover:
        entry["major_diff_rollover"] = major_rollover
    existing_ledger.append(entry)
    keep = max(1, int(max_entries))
    ledger = existing_ledger[-keep:]

    persisted = dict(payload)
    persisted[ledger_key] = ledger
    _write_json_object(path, persisted)
    return persisted


def write_json_with_diff_ledger(
    path: Path,
    payload_or_text: dict[str, Any] | str,
    *,
    ledger_key: str = "diff_ledger",
    max_entries: int = 30,
    max_sample_paths: int = 20,
) -> dict[str, Any]:
    if isinstance(payload_or_text, dict):
        payload = payload_or_text
    else:
        loaded = json.loads(payload_or_text)
        if not isinstance(loaded, dict):
            raise ValueError("diff-ledger write expects a JSON object payload")
        payload = loaded
    return write_payload_with_diff_ledger(
        path,
        payload,
        ledger_key=ledger_key,
        max_entries=max_entries,
        max_sample_paths=max_sample_paths,
    )
