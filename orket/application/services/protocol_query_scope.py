"""Captured protocol path authority; resolve only inside owned query workers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def resolve_protocol_run_root(workspace_root: Path, run_id: str) -> Path:
    workspace_root = workspace_root.resolve()
    base = (workspace_root / "runs").resolve()
    candidate = (base / str(run_id).strip()).resolve()
    if not base.is_relative_to(workspace_root) or not str(run_id).strip() or not candidate.is_relative_to(base):
        raise ValueError(f"Invalid run_id: {run_id}")
    if not (candidate / "events.log").resolve().is_relative_to(base):
        raise ValueError(f"Invalid run_id: events path escapes runs root: {run_id}")
    return candidate


def validate_protocol_replay_paths(events: Path, artifacts: Path | None, *, allowed_root: Path) -> None:
    """Validate observed file targets before replay; not a filesystem mutation fence."""
    root = allowed_root.resolve()
    paths = [events, events.with_name("receipts.log")]
    if artifacts is not None:
        paths.append(artifacts)
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Protocol query path escapes selected root: {path}")
    if artifacts is not None:
        for path in artifacts.rglob("*"):
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"Protocol query path escapes selected root: {path}")


@dataclass(frozen=True)
class ProtocolQueryScope:
    workspace_root: Path
    invocation_root: Path
    operator_paths: bool = False

    @classmethod
    def capture(cls, workspace_root: Path, operator_invocation_root: Path | None = None) -> ProtocolQueryScope:
        # Capture invocation location before awaiting; resolve symlinks in workers.
        invocation = Path.cwd() if operator_invocation_root is None else Path(operator_invocation_root)
        if not invocation.is_absolute():
            raise ValueError("Protocol invocation root must be absolute.")
        workspace = Path(workspace_root)
        if not workspace.is_absolute():
            workspace = invocation / workspace
        return cls(workspace, invocation, operator_invocation_root is not None)

    def operand(self, raw_path: str | Path, *, field_name: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (self.invocation_root if self.operator_paths else self.workspace_root) / candidate
        resolved = candidate.resolve()
        if not self.operator_paths and not resolved.is_relative_to(self.workspace_root.resolve()):
            raise ValueError(f"Invalid {field_name}: path escapes workspace root.")
        return resolved

    def replay_paths(self, run_id: str, events: str | None, artifacts: str | None) -> tuple[Path, Path | None]:
        root = resolve_protocol_run_root(self.workspace_root, run_id)
        events_path = self.operand(events, field_name="events") if events else root / "events.log"
        if not events_path.exists():
            raise FileNotFoundError(f"Protocol events log not found for run '{run_id}' at {events_path}.")
        artifact_root = self.operand(artifacts, field_name="artifacts") if artifacts else root / "artifacts"
        if not self.operator_paths:
            validate_protocol_replay_paths(events_path, artifact_root, allowed_root=self.workspace_root)
        return events_path, artifact_root if artifacts or artifact_root.exists() else None

    def runs_path(self, raw_path: str | None) -> Path:
        root = self.operand(raw_path or self.workspace_root / "runs", field_name="runs_root")
        if not root.exists():
            raise FileNotFoundError(f"Runs root not found: {root}")
        return root

    def sqlite_path(self, raw_path: str | None) -> Path:
        path = self.operand(raw_path or self.workspace_root / ".orket/durable/db/orket_persistence.db",
                            field_name="sqlite_db_path")
        if not path.exists():
            raise FileNotFoundError(f"SQLite run ledger database not found: {path}")
        return path
