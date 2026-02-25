from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _parse_dt(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


def _normalize_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lstrip("/")


def classify_namespace(path: str) -> str:
    normalized = _normalize_path(path)
    if normalized.startswith("smoke/"):
        return "smoke"
    if normalized.startswith("checks/"):
        return "checks"
    if normalized.startswith("artifacts/"):
        return "artifacts"
    if normalized.startswith("latest/"):
        return "latest"
    return "other"


def smoke_profile(path: str) -> str:
    parts = _normalize_path(path).split("/")
    if len(parts) >= 2 and parts[0] == "smoke":
        return parts[1] or "_unknown"
    return "_unknown"


def check_id(path: str) -> str:
    parts = _normalize_path(path).split("/")
    if len(parts) >= 3 and parts[0] == "checks":
        stem = Path(parts[2]).stem
        if "_pass" in stem:
            prefix = stem.split("_pass", 1)[0]
            if prefix:
                return prefix
        if "_fail" in stem:
            prefix = stem.split("_fail", 1)[0]
            if prefix:
                return prefix
        return stem or "_unknown"
    if parts:
        stem = Path(parts[-1]).stem
        return stem or "_unknown"
    return "_unknown"


def check_status(entry: Dict[str, Any]) -> str:
    raw = str(entry.get("status") or "").strip().lower()
    if raw in {"pass", "fail"}:
        return raw
    return "unknown"


def _entry_dt(entry: Dict[str, Any]) -> datetime:
    dt = _parse_dt(str(entry.get("updated_at") or ""))
    return dt or datetime(1970, 1, 1, tzinfo=UTC)


def _entry_size(entry: Dict[str, Any]) -> int:
    try:
        return max(0, int(entry.get("size_bytes") or 0))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class RetentionPolicy:
    smoke_days: int = 14
    smoke_keep_latest_per_profile: int = 50
    checks_days: int = 60
    artifacts_days: int = 30
    artifacts_size_cap_bytes: int = 200 * 1024 * 1024 * 1024


def _rank_latest(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(entries, key=lambda e: _entry_dt(e), reverse=True)


def build_retention_plan(
    entries: Iterable[Dict[str, Any]],
    *,
    as_of: datetime | None = None,
    policy: RetentionPolicy | None = None,
) -> Dict[str, Any]:
    policy = policy or RetentionPolicy()
    anchor = as_of or now_utc()
    rows = []
    for entry in entries:
        path = _normalize_path(str(entry.get("path") or ""))
        if not path:
            continue
        row = {
            "path": path,
            "namespace": classify_namespace(path),
            "updated_at": (_entry_dt(entry)).isoformat(),
            "size_bytes": _entry_size(entry),
            "pinned": bool(entry.get("pinned", False)),
            "status": check_status(entry),
        }
        rows.append(row)

    keep: Dict[str, Tuple[str, str]] = {}
    delete: Dict[str, Tuple[str, str]] = {}

    # Hard-protect pinned and latest namespace.
    for row in rows:
        if row["pinned"]:
            keep[row["path"]] = ("pinned", "pinned_item")
            continue
        if row["namespace"] == "latest":
            keep[row["path"]] = ("latest", "latest_pointer")

    # Smoke policy: keep newest N per profile, then age prune.
    smoke_groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row["namespace"] != "smoke":
            continue
        smoke_groups.setdefault(smoke_profile(row["path"]), []).append(row)
    for profile, group in smoke_groups.items():
        ordered = _rank_latest(group)
        for idx, row in enumerate(ordered):
            if row["path"] in keep:
                continue
            age_days = (anchor - _entry_dt(row)).days
            if idx < max(1, policy.smoke_keep_latest_per_profile):
                keep[row["path"]] = ("smoke", f"keep_latest_per_profile:{profile}")
            elif age_days >= int(policy.smoke_days):
                delete[row["path"]] = ("smoke", f"ttl_exceeded:{age_days}d")
            else:
                keep[row["path"]] = ("smoke", f"within_ttl:{age_days}d")

    # Checks policy: keep newest pass/fail per check, then age prune.
    check_groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row["namespace"] != "checks":
            continue
        check_groups.setdefault(check_id(row["path"]), []).append(row)
    for cid, group in check_groups.items():
        ordered = _rank_latest(group)
        newest_by_status: Dict[str, str] = {}
        for row in ordered:
            if row["status"] in {"pass", "fail"} and row["status"] not in newest_by_status:
                newest_by_status[row["status"]] = row["path"]
        for row in ordered:
            if row["path"] in keep:
                continue
            age_days = (anchor - _entry_dt(row)).days
            if row["path"] in newest_by_status.values():
                keep[row["path"]] = ("checks", f"newest_{row['status']}:{cid}")
            elif age_days >= int(policy.checks_days):
                delete[row["path"]] = ("checks", f"ttl_exceeded:{age_days}d")
            else:
                keep[row["path"]] = ("checks", f"within_ttl:{age_days}d")

    # Artifacts policy: age prune, then cap prune oldest unpinned.
    artifacts = [r for r in rows if r["namespace"] == "artifacts"]
    ordered_artifacts = _rank_latest(artifacts)
    for row in ordered_artifacts:
        if row["path"] in keep:
            continue
        age_days = (anchor - _entry_dt(row)).days
        if age_days >= int(policy.artifacts_days):
            delete[row["path"]] = ("artifacts", f"ttl_exceeded:{age_days}d")
        else:
            keep[row["path"]] = ("artifacts", f"within_ttl:{age_days}d")

    kept_artifacts = [r for r in ordered_artifacts if r["path"] in keep]
    kept_size = sum(r["size_bytes"] for r in kept_artifacts)
    if kept_size > int(policy.artifacts_size_cap_bytes):
        oldest_first = sorted(kept_artifacts, key=lambda r: _entry_dt(r))
        for row in oldest_first:
            if kept_size <= int(policy.artifacts_size_cap_bytes):
                break
            if row["pinned"] or row["path"] in delete:
                continue
            kept_size -= row["size_bytes"]
            keep.pop(row["path"], None)
            delete[row["path"]] = ("artifacts", "size_cap_prune")

    # Other namespace: keep by default.
    for row in rows:
        if row["path"] in keep or row["path"] in delete:
            continue
        keep[row["path"]] = (row["namespace"], "default_keep")

    actions: List[Dict[str, Any]] = []
    for row in rows:
        action = "keep"
        reason = keep.get(row["path"], (row["namespace"], "default_keep"))[1]
        if row["path"] in delete:
            action = "delete"
            reason = delete[row["path"]][1]
        actions.append(
            {
                "path": row["path"],
                "namespace": row["namespace"],
                "action": action,
                "reason": reason,
                "pinned": row["pinned"],
                "size_bytes": row["size_bytes"],
                "updated_at": row["updated_at"],
                "status": row["status"],
            }
        )
    actions.sort(key=lambda a: (a["namespace"], a["path"]))

    deleted = [a for a in actions if a["action"] == "delete"]
    kept = [a for a in actions if a["action"] == "keep"]
    return {
        "ok": True,
        "as_of": anchor.isoformat(),
        "policy": {
            "smoke_days": int(policy.smoke_days),
            "smoke_keep_latest_per_profile": int(policy.smoke_keep_latest_per_profile),
            "checks_days": int(policy.checks_days),
            "artifacts_days": int(policy.artifacts_days),
            "artifacts_size_cap_bytes": int(policy.artifacts_size_cap_bytes),
        },
        "summary": {
            "total_count": len(actions),
            "keep_count": len(kept),
            "delete_count": len(deleted),
            "delete_bytes": sum(int(a["size_bytes"]) for a in deleted),
        },
        "actions": actions,
    }
