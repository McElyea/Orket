from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .models import RELIABLE_MODE_ENV, RELIABLE_REQUIRE_CLEAN_GIT_ENV


class ReproducibilityEnforcer:
    """Reliable-mode guardrails for extension execution."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def reliable_mode_enabled(self) -> bool:
        raw = (os.getenv(RELIABLE_MODE_ENV, "true") or "").strip().lower()
        return raw not in {"0", "false", "no", "off"}

    def validate_required_materials(self, materials: Any) -> None:
        missing: list[str] = []
        for material in list(materials or []):
            rel = str(material or "").strip()
            if not rel:
                continue
            target = (self.project_root / rel).resolve()
            if not str(target).startswith(str(self.project_root)):
                raise ValueError(f"Material path escapes project root: {rel}")
            if not target.exists():
                missing.append(rel)
        if missing:
            raise FileNotFoundError("Required materials missing: " + ", ".join(sorted(missing)))

    def validate_clean_git_if_required(self) -> None:
        raw = (os.getenv(RELIABLE_REQUIRE_CLEAN_GIT_ENV, "false") or "").strip().lower()
        if raw not in {"1", "true", "yes", "on"}:
            return
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0:
            raise RuntimeError("Unable to validate git clean state")
        if status.stdout.strip():
            raise RuntimeError("Reliable Mode requires clean git state")
