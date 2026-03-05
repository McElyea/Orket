from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return (proc.stdout or "").strip()


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def newest_mtime(path: Path) -> datetime:
    if not path.is_dir():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    latest_file: datetime | None = None
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        try:
            ts = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        except OSError:
            continue
        if latest_file is None or ts > latest_file:
            latest_file = ts
    if latest_file is not None:
        return latest_file
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def git_is_clean_for_path(repo_root: Path, target_path: Path) -> bool:
    rel = target_path.resolve().relative_to(repo_root.resolve()).as_posix()
    out = _run(["git", "status", "--porcelain", "--", rel], cwd=repo_root)
    return out.strip() == ""


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "projects": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return {"version": 1, "projects": []}
    if not isinstance(data, dict):
        return {"version": 1, "projects": []}
    data.setdefault("version", 1)
    data.setdefault("projects", [])
    return data


def save_registry(path: Path, registry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


@dataclass
class CleanupConfig:
    repo_root: Path
    registry_path: Path
    archive_dir: Path
    archive_days: int = 45
    hard_delete_days: int = 90
    execute: bool = False
    source_dir: str | None = None
    projects: set[str] | None = None
    require_clean_git: bool = True


def _eligible(entry: dict[str, Any], cfg: CleanupConfig) -> bool:
    if cfg.source_dir and entry.get("source_dir") != cfg.source_dir:
        return False
    if cfg.projects and entry.get("project_name") not in cfg.projects:
        return False
    if entry.get("deleted_at"):
        return False
    if not entry.get("parity_verified"):
        return False
    return True


def apply_cleanup(cfg: CleanupConfig) -> dict[str, Any]:
    registry = load_registry(cfg.registry_path)
    now = datetime.now(UTC)

    archived = []
    deleted = []
    skipped = []

    for entry in registry.get("projects", []):
        if not _eligible(entry, cfg):
            continue

        local_path = Path(entry.get("local_path", "")).resolve()
        archived_path = Path(entry["archived_path"]).resolve() if entry.get("archived_path") else None

        if local_path.exists():
            try:
                last_change = newest_mtime(local_path)
            except OSError:
                skipped.append({"project": entry.get("project_name"), "reason": "stat_failed"})
                continue

            age_days = (now - last_change).days
            if age_days < cfg.archive_days:
                continue

            if cfg.require_clean_git and not git_is_clean_for_path(cfg.repo_root, local_path):
                skipped.append({"project": entry.get("project_name"), "reason": "git_dirty"})
                continue

            destination = cfg.archive_dir / f"{entry.get('project_name')}-{now.strftime('%Y%m%d-%H%M%S')}"
            if cfg.execute:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(local_path), str(destination))
                entry["archived_at"] = now.isoformat()
                entry["archived_path"] = str(destination)
            archived.append({"project": entry.get("project_name"), "from": str(local_path), "to": str(destination)})
            continue

        if archived_path and archived_path.exists():
            archived_at = parse_iso(entry.get("archived_at"))
            if not archived_at:
                skipped.append({"project": entry.get("project_name"), "reason": "missing_archived_at"})
                continue
            archived_age = (now - archived_at).days
            if archived_age < cfg.hard_delete_days:
                continue
            if cfg.execute:
                shutil.rmtree(archived_path)
                entry["deleted_at"] = now.isoformat()
            deleted.append({"project": entry.get("project_name"), "path": str(archived_path)})

    if cfg.execute:
        save_registry(cfg.registry_path, registry)

    return {
        "archived": archived,
        "deleted": deleted,
        "skipped": skipped,
        "execute": cfg.execute,
        "archive_days": cfg.archive_days,
        "hard_delete_days": cfg.hard_delete_days,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-cleanup policy for parity-verified published projects.")
    parser.add_argument("--repo-root", default=".", help="Monorepo root path.")
    parser.add_argument(
        "--registry-path",
        default=".orket/project_publish_registry.json",
        help="Registry path tracking published projects.",
    )
    parser.add_argument(
        "--archive-dir",
        default=".orket/local_archive/projects",
        help="Quarantine/archive folder before hard delete.",
    )
    parser.add_argument("--source-dir", default="", help="Optional source-dir filter (e.g., product, bin/projects).")
    parser.add_argument("--projects", nargs="*", default=[], help="Optional project-name filter.")
    parser.add_argument("--archive-days", type=int, default=45, help="Inactive days before archive move.")
    parser.add_argument("--hard-delete-days", type=int, default=90, help="Days in archive before hard delete.")
    parser.add_argument("--allow-dirty-git", action="store_true", help="Allow cleanup even when git path is dirty.")
    parser.add_argument("--execute", action="store_true", help="Apply changes. Default is dry-run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cfg = CleanupConfig(
        repo_root=repo_root,
        registry_path=(repo_root / args.registry_path).resolve(),
        archive_dir=(repo_root / args.archive_dir).resolve(),
        archive_days=max(1, int(args.archive_days)),
        hard_delete_days=max(1, int(args.hard_delete_days)),
        execute=args.execute,
        source_dir=args.source_dir.strip() or None,
        projects=set(p.strip() for p in args.projects if p.strip()) or None,
        require_clean_git=not args.allow_dirty_git,
    )
    result = apply_cleanup(cfg)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
