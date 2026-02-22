#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    fixture: str
    expected_exit: int
    required_tokens: tuple[str, ...]


SCENARIOS = (
    Scenario(
        name="missing_manifest",
        fixture="missing_manifest",
        expected_exit=1,
        required_tokens=("E_TRIPLET_INCOMPLETE",),
    ),
    Scenario(
        name="forbidden_token",
        fixture="bad_id",
        expected_exit=1,
        required_tokens=("E_POLICY_RAW_ID_FORBIDDEN",),
    ),
    Scenario(
        name="valid_triplet",
        fixture="valid_user",
        expected_exit=0,
        required_tokens=("I_TRIPLET_COMPLETE", "I_VOCAB_LINKS_RESOLVED", '"related_stems":["account","profile"]'),
    ),
)


def _run_scenario(scenario: Scenario) -> tuple[bool, str]:
    env = dict(os.environ)
    env["LOG_FORMAT_VERSION"] = "2"
    env["ENABLED_SENTINEL_PLUGINS"] = "related_stems"

    cmd = [
        sys.executable,
        "tools/ci/orket_sentinel.py",
        "--test-fixture",
        scenario.fixture,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    output = (proc.stdout or "") + (proc.stderr or "")

    if proc.returncode != scenario.expected_exit:
        return False, (
            f"scenario={scenario.name} expected_exit={scenario.expected_exit} "
            f"actual_exit={proc.returncode}\n{output}"
        )

    missing = [token for token in scenario.required_tokens if token not in output]
    if missing:
        return False, f"scenario={scenario.name} missing_tokens={missing}\n{output}"

    return True, f"scenario={scenario.name} PASS"


def main() -> int:
    failures: list[str] = []
    for scenario in SCENARIOS:
        ok, message = _run_scenario(scenario)
        print(message)
        if not ok:
            failures.append(message)

    if failures:
        print(f"sentinel_fire_drill=FAIL failures={len(failures)}")
        return 1
    print("sentinel_fire_drill=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
