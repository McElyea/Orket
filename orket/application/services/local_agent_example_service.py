"""A prepared two-iteration ticket report through the existing governed-agent owner."""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.local_agent_example_store import (
    allocate_example,
    publish_example_inputs,
    publish_example_result,
)
from orket.application.services.extension_scaffold_service import create_external_extension
from orket.application.services.governed_agent_example_inputs import (
    live_ticket_report_request,
    ticket_continuation_inputs,
)
from orket.application.services.governed_agent_submission_service import (
    GovernedAgentProviderOptions,
    GovernedAgentSubmission,
    submit_governed_agent,
)
from orket.application.services.local_runtime_diagnostics import diagnose_local_runtime


async def run_local_agent_example(
    root: Path, *, target: Path, now: datetime, environment: Mapping[str, str],
) -> dict[str, Any]:
    if not root.is_absolute() or not target.is_absolute():
        raise ValueError("E_LOCAL_EXAMPLE_ABSOLUTE_PATH_REQUIRED")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("E_LOCAL_EXAMPLE_AWARE_TIME_REQUIRED")
    captured = dict(environment)
    captured.update(ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL="0", ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL="0")
    request = live_ticket_report_request("mixed", now=now)
    request_bytes = json.dumps(request, ensure_ascii=False, indent=2).encode("utf-8")
    continuation = json.dumps(ticket_continuation_inputs(), ensure_ascii=False, indent=2).encode("utf-8")
    diagnostic = await diagnose_local_runtime(root, environment=captured)
    if not diagnostic["ok"]:
        return {"ok": False, "error": "Local runtime is not ready; inspect diagnostics.", "diagnostic": diagnostic,
                "observed_path": diagnostic["observed_path"], "observed_result": diagnostic["observed_result"]}
    area = await run_owned_thread(partial(allocate_example, root, target), label="local-agent-example-allocation")
    scaffold = await create_external_extension(area / "extension", template_kind="agent")
    if not scaffold["ok"]:
        raise RuntimeError(f"E_LOCAL_EXAMPLE_SCAFFOLD: {scaffold['errors']}")
    await run_owned_thread(partial(publish_example_inputs, area, request_bytes, continuation),
                           label="local-agent-example-inputs")
    submission = GovernedAgentSubmission(
        workload_id="governed-agent-loop", project_root=root, catalog_path=area / "catalog.json",
        request_path=area / "request.json", continuation_inputs_path=area / "continuation.json",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=tuple((now + timedelta(seconds=ordinal)).isoformat() for ordinal in (1, 2)),
        next_lease_expiries_utc=((now + timedelta(minutes=9)).isoformat(),),
        provider=GovernedAgentProviderOptions(provider_name=diagnostic["provider"], model=diagnostic["model"],
                                              provider_base_url=diagnostic["base_url"]),
    )
    result = await submit_governed_agent(db_path=area / "agent.sqlite3", submission=submission,
                                         invocation_root=root, environment=captured)
    result["example"] = {"directory": str(area), "report": str(area / "report.json"),
                          "scope": "Prepared ticket counts with actual selected-provider inference; Metal unverified"}
    encoded = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    await run_owned_thread(partial(publish_example_result, area, encoded), label="local-agent-example-result")
    return result
