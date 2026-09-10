# Layer: end-to-end

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from orket.interfaces.api import create_api_app
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import staged_agent_request, ticket_continuation_inputs

_LIVE_ENABLED = os.getenv("ORKET_RUN_LIVE_AGENT_OLLAMA") == "1"
_EXTENSION_ROOT = Path(
    os.getenv(
        "ORKET_GOVERNED_AGENT_EXTENSION_ROOT",
        r"C:\Source\Orket-Extensions\GovernedLocalAgent",
    )
)


@pytest.mark.end_to_end
@pytest.mark.skipif(not _LIVE_ENABLED, reason="set ORKET_RUN_LIVE_AGENT_OLLAMA=1 for live Ollama proof")
def test_live_multi_model_wake_reaches_truth_through_api_supervisor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. A durable API wake crosses the live API-owned multi-model supervisor."""
    if not _EXTENSION_ROOT.is_dir():
        pytest.fail(f"Live external extension is missing: {_EXTENSION_ROOT}")
    planner = os.getenv("ORKET_GOVERNED_AGENT_PLANNER_MODEL", "qwen2.5:7b")
    actor = os.getenv("ORKET_GOVERNED_AGENT_ACTOR_MODEL", "qwen2.5-coder:7b")
    critic = os.getenv("ORKET_GOVERNED_AGENT_CRITIC_MODEL", planner)
    catalog_path = _write_catalog(tmp_path)
    db_path = tmp_path / "agent.sqlite3"
    _configure_api(
        monkeypatch,
        db_path=db_path,
        catalog_path=catalog_path,
        planner=planner,
        actor=actor,
        critic=critic,
    )
    app = create_api_app(project_root=tmp_path)
    payload = _wake_payload()
    payload["dispatch"]["request"]["admitted_capabilities"].append("memory.query")
    payload["dispatch"]["request"]["extension_config"] = {"objective_memory": True}
    with TestClient(app) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=payload)
        assert admitted.status_code == 202, admitted.json()
        wake_id = admitted.json()["wake"]["wake_id"]
        wake = _wait_for_terminal_wake(client, wake_id)
        inspection = client.get("/v1/agent-runs/run-1", headers=_headers())

        assert wake["state"] == "completed", wake
        assert inspection.status_code == 200, inspection.json()
        body = inspection.json()
        assert body["run"]["lifecycle_state"] == "completed"
        assert [item["decision"]["disposition"] for item in body["iterations"]] == [
            "continue",
            "complete",
        ]
        receipts = _receipts(body)
        role_models = {receipt["role"]: receipt["model"] for receipt in receipts}
        assert role_models == {"planner": planner, "actor": actor, "critic": critic}
        assert len(set(role_models.values())) >= 2
        assert all(receipt["usage_posture"] == "measured" for receipt in receipts)
        memory_calls = [call for iteration in body["iterations"] for call in iteration["model_calls"]
                        if call["operation"] == "memory.query.v1"]
        assert len(memory_calls) == 2 and all(call["status"] == "completed" for call in memory_calls)

    assert app.state.api_runtime_context.active_background_task_count == 0


def _configure_api(
    monkeypatch,
    *,
    db_path: Path,
    catalog_path: Path,
    planner: str,
    actor: str,
    critic: str,
) -> None:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_DB_PATH", str(db_path))
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_PROVIDER", "ollama")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "1")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_PLANNER_MODEL", planner)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_ACTOR_MODEL", actor)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CRITIC_MODEL", critic)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CAPACITY_LIMIT", "1")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CLAIM_LEASE_SECONDS", "180")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CLAIM_RENEWAL_SECONDS", "5")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_IDLE_WAIT_SECONDS", "0.05")


def _write_catalog(tmp_path: Path) -> Path:
    manifest_path = _EXTENSION_ROOT / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog_path = tmp_path / "extensions.json"
    catalog_path.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": manifest["extension_id"],
                        "extension_version": manifest["extension_version"],
                        "extension_api_version": "1.0.0",
                        "source": "live-supervisor-proof",
                        "path": str(_EXTENSION_ROOT.resolve()),
                        "contract_style": "sdk_v0",
                        "manifest_path": str(manifest_path.resolve()),
                        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"],
                        "manifest_entries": manifest["workloads"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return catalog_path


def _wake_payload() -> dict:
    now = datetime.now(UTC)
    request = _live_request(now)
    return {
        "occurrence_id": "live-supervisor-proof-1",
        "target_kind": "new_run",
        "workload_id": "governed-agent-loop",
        "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1",
            "continuation_inputs": ticket_continuation_inputs(),
            "request": request,
            "creation_timestamp_utc": now.isoformat(),
            "decision_timestamps_utc": [
                (now + timedelta(seconds=1)).isoformat(),
                (now + timedelta(seconds=2)).isoformat(),
            ],
            "next_lease_expiries_utc": [(now + timedelta(minutes=9)).isoformat()],
        },
    }


def _live_request(now: datetime) -> dict:
    request = staged_agent_request()
    request["deadline_utc"] = (now + timedelta(minutes=10)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(minutes=9)).isoformat()
    for profile in request["model_profiles"]:
        profile["max_output_tokens"] = 512
        profile["timeout_ms"] = 120_000
    for scope in ("remaining_iteration_budget", "remaining_run_budget"):
        multiplier = 2 if scope == "remaining_run_budget" else 1
        budget = request[scope]
        budget["model_calls"] = 4 * multiplier
        budget["per_role_model_calls"] = [
            {"role": role, "count": 2 * multiplier}
            for role in ("planner", "actor", "critic")
        ]
        budget["input_tokens"] = 16_384 * multiplier
        budget["output_tokens"] = 2_048 * multiplier
        budget["repair_attempts"] = multiplier
        budget["wall_time_ms"] = 600_000
        budget["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in budget.items() if key != "snapshot_digest"}
        )
    return request


def _wait_for_terminal_wake(client: TestClient, wake_id: str) -> dict:
    for _ in range(1800):
        response = client.get(f"/v1/agent-wakes/{wake_id}", headers=_headers())
        assert response.status_code == 200
        wake = response.json()
        if wake["state"] in {"completed", "cancelled", "recovery_required"}:
            return wake
        time.sleep(0.1)
    raise AssertionError("live governed-agent wake did not reach a terminal queue state")


def _receipts(inspection: dict) -> list[dict]:
    return [
        call["receipt"]
        for iteration in inspection["iterations"]
        for call in iteration["model_calls"]
        if call["receipt"] is not None
    ]


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-key"}
