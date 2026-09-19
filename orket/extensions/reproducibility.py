from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.application.services.command_process_supervisor import CommandProcessSupervisor


class ReproducibilityEnforcer:
    """Reliable-mode guardrails for extension execution."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def validate_required_materials(self, materials: Any) -> None:
        root = self.project_root.resolve()
        missing: list[str] = []
        for material in list(materials or []):
            rel = str(material or "").strip()
            if not rel:
                continue
            target = (root / rel).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"Material path escapes project root: {rel}")
            if not target.exists():
                missing.append(rel)
        if missing:
            raise FileNotFoundError("Required materials missing: " + ", ".join(sorted(missing)))

    async def validate_clean_git_if_required(self, *, required: bool) -> None:
        if not required:
            return
        owner = CommandProcessSupervisor(self.project_root, cancellation_event="extension_git_status_cancelled")
        status = await owner.run(["git", "status", "--porcelain"], cwd=self.project_root, timeout_seconds=30)
        if not status.cleanup_confirmed or not status.capture_complete or status.reason != "completed" or status.returncode != 0:
            raise RuntimeError(f"Unable to validate git clean state: {status.reason}")
        if status.stdout.strip():
            raise RuntimeError("Reliable Mode requires clean git state")
