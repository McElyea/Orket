from __future__ import annotations

import json
from typing import Any

from orket_extension_sdk.result import WorkloadResult


def run(ctx: Any, payload: dict[str, Any]) -> WorkloadResult:
    """Template workload entrypoint.

    Replace this logic with real extension behavior. Keep runtime authority
    interactions behind SDK capability calls.
    """
    return WorkloadResult(
        ok=True,
        output={"echo": payload},
        artifacts=[],
        issues=[],
    )


if __name__ == "__main__":
    print(json.dumps(run(ctx=None, payload={"message": "template"}).model_dump(), indent=2))
