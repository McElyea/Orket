from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PackMetadata:
    pack_id: str
    pack_version: str
    extends: str | None
    path: Path


@dataclass(frozen=True)
class ModeSpec:
    mode_id: str
    description: str
    hard_rules: tuple[str, ...]
    soft_rules: tuple[str, ...]
    required_outputs: tuple[str, ...]
    suite_ref: str
    rubric: dict[str, object]
    path: Path

