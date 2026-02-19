from __future__ import annotations

import os
import shutil
from pathlib import Path


def durable_root() -> Path:
    raw = os.getenv("ORKET_DURABLE_ROOT", "").strip()
    return Path(raw) if raw else (Path.cwd() / ".orket" / "durable")


def _migrate_legacy_file(*, legacy: Path, target: Path) -> None:
    if not legacy.exists() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target))


def _migrate_legacy_dir(*, legacy: Path, target: Path) -> None:
    if not legacy.exists() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy), str(target))


def resolve_runtime_db_path(db_path: str | None = None) -> str:
    if db_path:
        return db_path
    target = durable_root() / "db" / "orket_persistence.db"
    _migrate_legacy_file(legacy=Path.cwd() / "orket_persistence.db", target=target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)


def resolve_webhook_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    target = durable_root() / "db" / "webhook.db"
    _migrate_legacy_file(legacy=Path.cwd() / ".orket" / "webhook.db", target=target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def resolve_live_acceptance_db_path(db_path: str | None = None) -> str:
    if db_path:
        return db_path
    legacy = Path.cwd() / "workspace" / "observability" / "live_acceptance_loop.db"
    target = durable_root() / "observability" / "live_acceptance_loop.db"
    _migrate_legacy_file(legacy=legacy, target=target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)


def resolve_user_settings_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    target = durable_root() / "config" / "user_settings.json"
    _migrate_legacy_file(legacy=Path.cwd() / "user_settings.json", target=target)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def resolve_user_preferences_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    target = durable_root() / "config" / "preferences.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def resolve_gitea_artifact_cache_root(path: str | None = None) -> Path:
    if path:
        return Path(path)
    target = durable_root() / "gitea_artifacts"
    _migrate_legacy_dir(legacy=Path.cwd() / ".orket" / "gitea_artifacts", target=target)
    target.mkdir(parents=True, exist_ok=True)
    return target
