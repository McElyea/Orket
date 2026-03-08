from __future__ import annotations

from pathlib import Path


def default_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_model_root(project_root: Path | None = None) -> Path:
    root = Path(project_root).resolve() if project_root is not None else default_project_root()
    return root / "model"


def default_workspace_root(project_root: Path | None = None) -> Path:
    root = Path(project_root).resolve() if project_root is not None else default_project_root()
    return root / "workspace" / "default"
