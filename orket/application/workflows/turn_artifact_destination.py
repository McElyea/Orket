"""One captured identity and path authority for an admitted turn's artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from orket.application.services.turn_tool_control_plane_support import run_id_for
from orket.naming import sanitize_name

if TYPE_CHECKING:
    from .turn_artifact_writer import TurnArtifactWriter


def artifact_component(value: str, *, field: str, sanitize: bool = True) -> str:
    """Refuse lexical redirection; this does not resolve or confine symlinks."""
    token = sanitize_name(value) if sanitize else value
    windows = PureWindowsPath(token)
    if token in ("", ".", "..") or any(char in token for char in ("/", "\\", "\0")) or windows.drive or windows.root:
        raise ValueError(f"E_TURN_ARTIFACT_PATH_COMPONENT:{field}")
    return token


@dataclass(frozen=True, slots=True)
class TurnArtifactDestination:
    writer: TurnArtifactWriter
    workspace: Path
    session_id: str
    issue_id: str
    role_name: str
    role_id: str | None
    turn_index: int

    def __post_init__(self) -> None:
        if not self.workspace.is_absolute():
            raise ValueError("E_TURN_ARTIFACT_WORKSPACE_NOT_CAPTURED")
        for field in ("session_id", "issue_id", "role_name"):
            artifact_component(getattr(self, field), field=field)

    def require_writer(self, writer: TurnArtifactWriter) -> None:
        if writer is not self.writer:
            raise ValueError("E_TURN_ARTIFACT_WRITER_MISMATCH")

    def output_dir_for_turn(self, turn_index: int) -> Path:
        return (
            self.workspace / "observability"
            / artifact_component(self.session_id, field="session_id")
            / artifact_component(self.issue_id, field="issue_id")
            / f"{turn_index:03d}_{artifact_component(self.role_name, field='role_name')}"
        )

    @property
    def output_dir(self) -> Path:
        return self.output_dir_for_turn(self.turn_index)

    @property
    def control_plane_run_id(self) -> str:
        return run_id_for(session_id=self.session_id, issue_id=self.issue_id,
                          role_name=self.role_name, turn_index=self.turn_index)

    def file_path(self, filename: str) -> Path:
        return self.output_dir / artifact_component(filename, field="filename", sanitize=False)
