from pathlib import Path


def test_unittest_mock_usage_is_minimized():
    tests_root = Path("tests")
    allowlist = {
        Path("tests/application/test_orchestrator_epic.py"),
        Path("tests/integration/test_mock_policy.py"),
    }
    offenders = []

    for path in tests_root.rglob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        if "unittest.mock" in text and path not in allowlist:
            offenders.append(str(path))

    assert offenders == [], (
        "Avoid unittest.mock in unit tests when possible. "
        f"Unexpected usage in: {offenders}"
    )

