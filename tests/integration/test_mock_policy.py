from pathlib import Path

import pytest

from scripts.common.git_inventory import git_list_files

pytestmark = pytest.mark.contract


def test_unittest_mock_usage_is_minimized():
    tests_root = Path(__file__).resolve().parents[1]
    repo_root = tests_root.parent
    allowlist = {
        Path("tests/application/test_orchestrator_epic.py"),
        Path("tests/integration/test_mock_policy.py"),
    }
    offenders = []

    for path in git_list_files(repo_root):
        if not path.is_relative_to(tests_root) or not path.match("test_*.py"):
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(repo_root)
        if "unittest.mock" in text and relative not in allowlist:
            offenders.append(relative.as_posix())

    assert offenders == [], (
        "Avoid unittest.mock in unit tests when possible. "
        f"Unexpected usage in: {offenders}"
    )
