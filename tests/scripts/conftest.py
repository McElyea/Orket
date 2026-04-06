# LIFECYCLE: live
from __future__ import annotations

import os
from pathlib import Path

import pytest

_LIFECYCLE_PREFIX = "# LIFECYCLE:"
_ONE_SHOT_ENV = "ORKET_INCLUDE_ONE_SHOT_SCRIPT_TESTS"


def _read_lifecycle(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:3]:
            normalized = str(line).strip()
            if not normalized.startswith(_LIFECYCLE_PREFIX):
                continue
            return normalized.partition(":")[2].strip().lower()
    except OSError:
        return ""
    return ""


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    include_one_shot = str(os.environ.get(_ONE_SHOT_ENV) or "").strip().lower() in {"1", "true", "yes", "on"}
    archived_skip = pytest.mark.skip(reason="archived script test")
    one_shot_skip = pytest.mark.skip(reason=f"one-shot script test; set {_ONE_SHOT_ENV}=1 to include")

    for item in items:
        path = Path(str(item.fspath))
        lifecycle = _read_lifecycle(path)
        if lifecycle == "archived":
            item.add_marker(archived_skip)
        elif lifecycle == "one-shot" and not include_one_shot:
            item.add_marker(one_shot_skip)
