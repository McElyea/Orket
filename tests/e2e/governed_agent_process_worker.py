"""Test-only API process fault injection; never installed as runtime code."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Also works from the acceptance harness, which contains tests but no core source.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient  # noqa: E402

from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor  # noqa: E402
from orket.interfaces.api import create_api_app  # noqa: E402
from tests.e2e.test_governed_agent_effect_ollama import (  # noqa: E402
    _assert_terminal,
    _effect_payload,
    _inspect,
    _pause_for_approval,
)
from tests.e2e.test_governed_agent_supervisor_ollama import _headers, _wait_for_terminal_wake  # noqa: E402


def crash(root: Path, point: str) -> None:
    payload = _effect_payload()
    report = root / "reports/ticket-report.json"
    blocked = _pause_for_approval(root, payload, report)
    deadline = datetime.fromisoformat(payload["dispatch"]["request"]["deadline_utc"])
    resolution = {"decision": "approved", "actor_ref": "operator:process-proof",
                  "timestamp_utc": datetime.now(UTC).isoformat(),
                  "next_lease_expires_at_utc": (deadline - timedelta(seconds=1)).isoformat(),
                  "decision_timestamps_utc": [(deadline - timedelta(seconds=2)).isoformat()],
                  "next_lease_expiries_utc": []}
    route = f"/v1/agent-runs/run-1/effects/{blocked['approvals'][0]['request_id']}/resolve"
    (root / "resolution.json").write_text(json.dumps({"route": route, "payload": resolution}), encoding="utf-8")
    real_write = GovernedAgentFileEffectExecutor.write

    async def crash_at_write(self, **kwargs):
        if point == "after_write":
            result = await real_write(self, **kwargs)
            assert result["ok"], result
        os._exit(93)

    GovernedAgentFileEffectExecutor.write = crash_at_write
    os.environ["ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED"] = "0"
    with TestClient(create_api_app(project_root=root)) as client:
        client.post(route, headers=_headers(), json=resolution)
    raise AssertionError("fault injection did not terminate the API process")


def recover(root: Path, point: str) -> None:
    saved = json.loads((root / "resolution.json").read_text(encoding="utf-8"))
    report = root / "reports/ticket-report.json"
    before = report.stat().st_mtime_ns if report.exists() else None
    os.environ["ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED"] = "1"

    async def forbidden_write(self, **kwargs):
        raise AssertionError("recovery must only observe, never repeat a write")

    GovernedAgentFileEffectExecutor.write = forbidden_write
    app = create_api_app(project_root=root)
    with TestClient(app) as client:
        response = client.post(saved["route"], headers=_headers(), json=saved["payload"])
        if point == "before_write":
            assert response.status_code == 400, response.text
            assert "E_AGENT_EFFECT_RECONCILIATION_REQUIRED" in response.text
            assert not report.exists()
            assert _inspect(client)["run"]["lifecycle_state"] == "operator_blocked"
        else:
            assert response.status_code == 200, response.text
            wake = _wait_for_terminal_wake(client, response.json()["wake"]["wake_id"])
            assert wake["state"] == "completed", wake
            final = _inspect(client)
            _assert_terminal(final, "approved", report)
            assert report.stat().st_mtime_ns == before
            assert client.get("/v1/agent-runs/run-1/replay", headers=_headers()).json()["status"] == "matched"
            assert _inspect(client) == final
    assert app.state.api_runtime_context.active_background_task_count == 0
    print(json.dumps({"point": point, "observed_path": "primary", "observed_result": "success",
                      "proof": "API process exited 93 at write boundary; fresh process observed without writing"}))


if __name__ == "__main__":
    {"crash": crash, "recover": recover}[sys.argv[2]](Path(sys.argv[1]), sys.argv[3])
