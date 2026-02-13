from __future__ import annotations

import json
from datetime import datetime, UTC, timedelta
from pathlib import Path

from scripts.cleanup_published_projects import CleanupConfig, apply_cleanup


def _write_registry(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_archive_inactive_parity_verified_project(tmp_path):
    repo_root = tmp_path
    source_dir = repo_root / "product"
    project_dir = source_dir / "demo"
    project_dir.mkdir(parents=True)
    (project_dir / "a.txt").write_text("hello", encoding="utf-8")

    old = datetime.now(UTC) - timedelta(days=60)
    old_epoch = old.timestamp()
    (project_dir / "a.txt").touch()
    import os
    os.utime(project_dir / "a.txt", (old_epoch, old_epoch))

    registry_path = repo_root / ".orket" / "project_publish_registry.json"
    _write_registry(
        registry_path,
        {
            "version": 1,
            "projects": [
                {
                    "source_dir": "product",
                    "project_name": "demo",
                    "local_path": str(project_dir),
                    "parity_verified": True,
                    "last_published_at": old.isoformat(),
                    "deleted_at": None,
                    "archived_at": None,
                    "archived_path": None,
                }
            ],
        },
    )

    cfg = CleanupConfig(
        repo_root=repo_root,
        registry_path=registry_path,
        archive_dir=repo_root / ".orket" / "local_archive" / "projects",
        archive_days=45,
        hard_delete_days=90,
        execute=True,
        require_clean_git=False,
    )
    result = apply_cleanup(cfg)
    assert len(result["archived"]) == 1
    assert not project_dir.exists()


def test_hard_delete_archived_project_after_threshold(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".orket" / "local_archive" / "projects"
    archived = archive_dir / "demo-20250101-000000"
    archived.mkdir(parents=True)
    (archived / "a.txt").write_text("hello", encoding="utf-8")

    archived_at = (datetime.now(UTC) - timedelta(days=120)).isoformat()
    registry_path = repo_root / ".orket" / "project_publish_registry.json"
    _write_registry(
        registry_path,
        {
            "version": 1,
            "projects": [
                {
                    "source_dir": "product",
                    "project_name": "demo",
                    "local_path": str(repo_root / "product" / "demo"),
                    "parity_verified": True,
                    "deleted_at": None,
                    "archived_at": archived_at,
                    "archived_path": str(archived),
                }
            ],
        },
    )

    cfg = CleanupConfig(
        repo_root=repo_root,
        registry_path=registry_path,
        archive_dir=archive_dir,
        archive_days=45,
        hard_delete_days=90,
        execute=True,
        require_clean_git=False,
    )
    result = apply_cleanup(cfg)
    assert len(result["deleted"]) == 1
    assert not archived.exists()

