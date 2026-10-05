"""Retained per-invocation project assets; never mutate the caller's board."""
from __future__ import annotations

import json
import shutil
from pathlib import Path


def prepare_project(source: Path, destination: Path, department: str) -> Path:
    if not department or any(char in department for char in "/\\:") or department in {".", ".."}:
        raise ValueError("Benchmark department must be a single directory name")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    for root in ("model", "config"):
        origin = source / root
        if origin.exists():
            shutil.copytree(origin, destination / root, ignore=shutil.ignore_patterns("rocks", "epics"))
    for name in ("main.py", "CURRENT_AUTHORITY.md", "docs/RUNBOOK.md", "docs/ROADMAP.md"):
        origin = source / name
        if origin.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
    board = destination / "model" / department / "rocks/run_the_business.json"
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(json.dumps({"name": "Isolated benchmark", "epics": []}), encoding="utf-8")
    settings = destination / ".orket/durable/config"
    settings.mkdir(parents=True)
    (settings / "user_settings.json").write_text('{"setup_complete":true}', encoding="utf-8")
    (settings / "user_preferences.json").write_text('{}', encoding="utf-8")
    return destination


def project_environment(environment: dict[str, str], project: Path) -> dict[str, str]:
    return dict(environment, ORKET_DURABLE_ROOT=str(project / ".orket/durable"), ORKET_DISABLE_SANDBOX="1")
