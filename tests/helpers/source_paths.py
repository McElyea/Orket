"""Structural test paths use the actual imported package and copied repo tooling."""

from pathlib import Path

import orket

REPO_ROOT = Path(__file__).resolve().parents[2]
ORKET_ROOT = Path(orket.__file__).resolve().parent


def source_path(relative: str) -> Path:
    path = Path(relative)
    return ORKET_ROOT / path.relative_to("orket") if path.is_relative_to("orket") else REPO_ROOT / path


def relative_source_path(path: Path) -> str:
    if path.is_relative_to(ORKET_ROOT):
        return "orket/" + path.relative_to(ORKET_ROOT).as_posix()
    return path.relative_to(REPO_ROOT).as_posix()
