from __future__ import annotations

import re
import subprocess
import argparse
from pathlib import Path


ROADMAP_PATH = Path("docs/ROADMAP.md")


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout + result.stderr


def _extract_expected_metrics(roadmap_text: str) -> tuple[int | None, int | None]:
    passed_match = re.search(r"`python -m pytest tests/ -q` -> (\d+) passed\.", roadmap_text)
    collected_match = re.search(r"`python -m pytest --collect-only -q` -> (\d+) collected\.", roadmap_text)
    if not passed_match or not collected_match:
        return None, None
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
    parser = argparse.ArgumentParser(description="Check ROADMAP pytest metrics against live pytest output.")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Only validate collected count (fast mode for CI pre-gates).",
    )
    args = parser.parse_args()

    roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")
    expected_passed, expected_collected = _extract_expected_metrics(roadmap_text)
    if expected_passed is None or expected_collected is None:
        print("Roadmap metrics check skipped: expected pytest metric lines not present in docs/ROADMAP.md")
        return

    actual_collected = _extract_actual_collected(_run(["python", "-m", "pytest", "--collect-only", "-q"]))
    actual_passed = expected_passed
    if not args.quick:
        actual_passed = _extract_actual_passed(_run(["python", "-m", "pytest", "tests/", "-q"]))

    failures = []
    if not args.quick and expected_passed != actual_passed:
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
