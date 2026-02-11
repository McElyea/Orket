from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROADMAP_PATH = Path("docs/ROADMAP.md")


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def _extract_expected_metrics(roadmap_text: str) -> tuple[int, int]:
    passed_match = re.search(r"`python -m pytest tests/ -q` -> (\d+) passed\.", roadmap_text)
    collected_match = re.search(r"`python -m pytest --collect-only -q` -> (\d+) collected\.", roadmap_text)
    if not passed_match or not collected_match:
        raise SystemExit("Could not parse expected pytest metrics from docs/ROADMAP.md")
    return int(passed_match.group(1)), int(collected_match.group(1))


def _extract_actual_passed(pytest_output: str) -> int:
    match = re.search(r"(\d+)\s+passed", pytest_output)
    if not match:
        raise SystemExit("Could not parse actual passed count from pytest output")
    return int(match.group(1))


def _extract_actual_collected(collect_output: str) -> int:
    match = re.search(r"(\d+)\s+tests collected", collect_output)
    if not match:
        raise SystemExit("Could not parse actual collected count from pytest --collect-only output")
    return int(match.group(1))


def main() -> None:
    roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")
    expected_passed, expected_collected = _extract_expected_metrics(roadmap_text)

    actual_passed = _extract_actual_passed(_run(["python", "-m", "pytest", "tests/", "-q"]))
    actual_collected = _extract_actual_collected(_run(["python", "-m", "pytest", "--collect-only", "-q"]))

    failures = []
    if expected_passed != actual_passed:
        failures.append(f"ROADMAP passed mismatch: expected {expected_passed}, actual {actual_passed}")
    if expected_collected != actual_collected:
        failures.append(f"ROADMAP collected mismatch: expected {expected_collected}, actual {actual_collected}")

    if failures:
        print("Roadmap metric drift detected:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("Roadmap metrics check passed.")


if __name__ == "__main__":
    main()
