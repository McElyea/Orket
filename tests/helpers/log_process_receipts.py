"""Native process-identity readback shared by isolated logging proof harnesses."""

from typing import Any

import psutil


def process_readback(identities: dict[int, float | None]) -> dict[str, dict[str, Any]]:
    observed = {}
    for pid, expected_created in identities.items():
        try:
            actual_created = psutil.Process(pid).create_time()
        except psutil.NoSuchProcess:
            observed[str(pid)] = {"status": "absent", "expected_create_time": expected_created}
            continue
        status = "reused" if expected_created is not None and actual_created != expected_created else "present_same"
        observed[str(pid)] = {
            "status": status,
            "expected_create_time": expected_created,
            "actual_create_time": actual_created,
        }
    return observed
