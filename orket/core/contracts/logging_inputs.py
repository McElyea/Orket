"""Explicit immutable values used to select application log destinations and time."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOG_QUEUE_MAX = 10_000
LOG_QUEUE_MAX_ENV = "ORKET_LOG_QUEUE_MAX"
MISSING_WORKSPACE_MODE_ENV = "ORKET_LOGGING_MISSING_CONTEXT_MODE"
MISSING_WORKSPACE_MODE_LEGACY = "legacy_default"
MISSING_WORKSPACE_MODE_FAIL_FAST = "fail_fast"
MISSING_WORKSPACE_ERROR_CODE = "E_LOG_WORKSPACE_REQUIRED"
LOGGING_INPUT_ERROR = "E_LOGGING_PREPARATION_INPUT_UNSUPPORTED"


def log_queue_capacity(raw: str = "") -> int:
    if type(raw) is not str:
        raise TypeError(LOGGING_INPUT_ERROR)
    try:
        value = int(raw.strip())
    except ValueError:
        return DEFAULT_LOG_QUEUE_MAX
    return value if value > 0 else DEFAULT_LOG_QUEUE_MAX


@dataclass(frozen=True)
class LoggingInputs:
    invocation_root: Path
    timezone_name: str = "UTC"
    missing_workspace_mode: str = MISSING_WORKSPACE_MODE_LEGACY
    queue_max: int = DEFAULT_LOG_QUEUE_MAX

    def __post_init__(self) -> None:
        if type(self.invocation_root) is not type(Path()) or not self.invocation_root.is_absolute():
            raise ValueError("E_LOGGING_INVOCATION_ROOT_ABSOLUTE_REQUIRED")
        if type(self.timezone_name) is not str or type(self.missing_workspace_mode) is not str:
            raise TypeError(LOGGING_INPUT_ERROR)
        if self.missing_workspace_mode not in (MISSING_WORKSPACE_MODE_LEGACY, MISSING_WORKSPACE_MODE_FAIL_FAST):
            raise ValueError(LOGGING_INPUT_ERROR)
        if type(self.queue_max) is not int or self.queue_max <= 0:
            raise ValueError(LOGGING_INPUT_ERROR)

    @classmethod
    def select(cls, invocation_root: Path, *, timezone: str = "", missing_workspace: str = "",
               queue_max: str = "") -> LoggingInputs:
        if type(timezone) is not str or type(missing_workspace) is not str:
            raise TypeError(LOGGING_INPUT_ERROR)
        mode = (MISSING_WORKSPACE_MODE_FAIL_FAST if missing_workspace.strip().lower() ==
                MISSING_WORKSPACE_MODE_FAIL_FAST else MISSING_WORKSPACE_MODE_LEGACY)
        return cls(invocation_root, (timezone or "UTC").strip(), mode, log_queue_capacity(queue_max))

    def workspace(self, selected: Path | None) -> tuple[Path, dict[str, str]]:
        marker = {}
        if selected is None:
            if self.missing_workspace_mode == MISSING_WORKSPACE_MODE_FAIL_FAST:
                raise RuntimeError(f"{MISSING_WORKSPACE_ERROR_CODE}: log_event requires workspace when "
                                   f"{MISSING_WORKSPACE_MODE_ENV}={MISSING_WORKSPACE_MODE_FAIL_FAST}")
            selected = Path("workspace/default")
            marker = {"logging_context_mode": MISSING_WORKSPACE_MODE_LEGACY,
                      "logging_context_marker": "workspace_default_fallback"}
        if type(selected) is not type(Path()):
            raise TypeError(LOGGING_INPUT_ERROR)
        if selected.drive and not selected.is_absolute():
            raise ValueError("E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED")
        return (selected if selected.is_absolute() else self.invocation_root / selected), marker
