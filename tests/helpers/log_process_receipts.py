"""Native process-identity readback shared by isolated logging proof harnesses."""

import math
from typing import Any

import psutil


def _strict_creation_time(value: Any, *, code: str) -> int | float:
    if type(value) is int:
        if value > 0:
            return value
    elif type(value) is float and math.isfinite(value) and value > 0:
        return value
    raise ValueError(code)


def process_readback(identities: dict[int, float | None]) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for pid, expected_created in identities.items():
        if type(pid) is not int or pid <= 0:
            raise ValueError("E_PROCESS_READBACK_PID_INVALID")
        if expected_created is not None:
            _strict_creation_time(
                expected_created,
                code="E_PROCESS_READBACK_EXPECTED_CREATION_INVALID",
            )
        try:
            actual_created = psutil.Process(pid).create_time()
        except psutil.ZombieProcess:
            raise
        except psutil.NoSuchProcess:
            observed[str(pid)] = {"status": "absent", "expected_create_time": expected_created}
            continue
        actual_created = _strict_creation_time(
            actual_created,
            code="E_PROCESS_READBACK_OBSERVED_CREATION_INVALID",
        )
        if expected_created is None:
            status = "present_unknown"
        elif actual_created != expected_created:
            status = "reused"
        else:
            status = "present_same"
        observed[str(pid)] = {
            "status": status,
            "expected_create_time": expected_created,
            "actual_create_time": actual_created,
        }
    return observed
