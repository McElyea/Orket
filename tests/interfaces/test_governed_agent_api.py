# Layer: integration and end-to-end

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.interfaces.api import create_api_app
from orket.interfaces.orket_bundle_cli import main
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import agent_request


def test_api_wake_ingress_is_idempotent_and_survives_app_restart(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Authenticated ingress persists without requiring supervisor activation."""
    db_path = tmp_path / "agent.sqlite3"
    _configure_api(monkeypatch, db_path, enabled=False)
    payload = _wake_payload()

    first_app = create_api_app(project_root=tmp_path)
    with TestClient(first_app) as client:
        unauthorized = client.post("/v1/agent-wakes", json=payload)
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=payload)
        repeated = client.post("/v1/agent-wakes", headers=_headers(), json=payload)

    assert unauthorized.status_code == 403
    assert admitted.status_code == 202
    assert admitted.json()["status"] == "enqueued"
    assert repeated.status_code == 202
    assert repeated.json()["status"] == "idempotent"
    wake_id = admitted.json()["wake"]["wake_id"]

    second_app = create_api_app(project_root=tmp_path)
    with TestClient(second_app) as client:
        retained = client.get(f"/v1/agent-wakes/{wake_id}", headers=_headers())
        listed = client.get("/v1/agent-wakes", headers=_headers())

    assert retained.status_code == 200
    assert retained.json()["state"] == "queued"
    assert [item["wake_id"] for item in listed.json()["items"]] == [wake_id]
    assert second_app.state.api_runtime_context.active_background_task_count == 0


def test_api_wake_controls_are_authenticated_durable_and_evidence_gated(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. API control receipts survive restart and recovery fails closed without proof."""
    db_path = tmp_path / "agent.sqlite3"
    _configure_api(monkeypatch, db_path, enabled=False)
    with TestClient(create_api_app(project_root=tmp_path)) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=_wake_payload())
    wake_id = admitted.json()["wake"]["wake_id"]
    asyncio.run(_claim_wake(db_path))
    cancel_payload = {
        "action_id": "wake-action:api-cancel",
        "actor_ref": "operator:api",
        "timestamp_utc": "2026-09-07T12:00:00Z",
        "reason": "operator request",
        "expected_cancellation_epoch": 0,
        "cancellation_epoch": 1,
    }
    recovery_payload = {
        "action_id": "wake-action:api-recover",
        "actor_ref": "operator:api",
        "timestamp_utc": "2026-09-07T12:00:02Z",
        "reason": "reconciled child and effects",
        "expected_fencing_generation": 1,
        "resolution": "confirm_cancelled",
        "child_confirmed_stopped": True,
        "effect_uncertainty_cleared": True,
        "evidence_refs": ["process-reap:api", "effect-reconciliation:api"],
    }

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        unauthorized = client.post(f"/v1/agent-wakes/{wake_id}/cancel", json=cancel_payload)
        cancelled = client.post(f"/v1/agent-wakes/{wake_id}/cancel", headers=_headers(), json=cancel_payload)
        refused_payload = {
            **recovery_payload,
            "action_id": "wake-action:api-refused",
            "timestamp_utc": "2026-09-07T12:00:01Z",
            "child_confirmed_stopped": False,
        }
        refused = client.post(f"/v1/agent-wakes/{wake_id}/recover", headers=_headers(), json=refused_payload)
        recovered = client.post(f"/v1/agent-wakes/{wake_id}/recover", headers=_headers(), json=recovery_payload)
        listed = client.get(f"/v1/agent-wakes/{wake_id}/actions", headers=_headers())

    assert unauthorized.status_code == 403
    assert cancelled.status_code == 200 and cancelled.json()["wake"]["uncertainty"] is True
    assert refused.status_code == 409 and refused.json()["detail"]["status"] == "conflict"
    assert recovered.status_code == 200 and recovered.json()["wake"]["uncertainty"] is False
    assert [item["action_id"] for item in listed.json()["items"]] == [
        "wake-action:api-cancel",
        "wake-action:api-refused",
        "wake-action:api-recover",
    ]

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        retained = client.get(f"/v1/agent-wakes/{wake_id}/actions", headers=_headers())
    assert retained.json()["items"] == listed.json()["items"]
    assert retained.json()["items"][-1]["request"]["evidence_refs"] == recovery_payload["evidence_refs"]


def test_scheduled_wake_api_is_authenticated_durable_and_coalesced(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Schedule evaluation and selected wake survive API restart as one transaction."""
    db_path = tmp_path / "agent.sqlite3"
    _configure_api(monkeypatch, db_path, enabled=False)
    payload = _schedule_payload(evaluation_id="schedule-evaluation:api-1", include_prior=True)
    route = "/v1/agent-schedules/daily-report/evaluations"

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        unauthorized = client.post(route, json=payload)
        admitted = client.post(route, headers=_headers(), json=payload)
        replayed = client.post(route, headers=_headers(), json=payload)
        contradicted = client.post(
            route,
            headers=_headers(),
            json={**payload, "misfire_grace_seconds": 1},
        )

    assert unauthorized.status_code == 403
    assert admitted.status_code == 202 and admitted.json()["status"] == "enqueued"
    assert replayed.status_code == 202 and replayed.json()["status"] == "idempotent"
    assert contradicted.status_code == 409
    wake = admitted.json()["wake"]
    assert wake["source"] == "scheduled"
    assert wake["trigger"]["schedule_id"] == "daily-report"
    assert len(wake["trigger"]["coalesced_occurrence_ids"]) == 1

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        evaluations = client.get(route, headers=_headers())
        retained = client.get(f"/v1/agent-wakes/{wake['wake_id']}", headers=_headers())
    assert evaluations.status_code == 200
    assert [item["evaluation_id"] for item in evaluations.json()["items"]] == [
        "schedule-evaluation:api-1"
    ]
    assert retained.json()["trigger"] == wake["trigger"]


def test_api_owned_supervisor_dispatches_scheduled_wake(tmp_path: Path, monkeypatch) -> None:
    """Layer: end-to-end. Authenticated scheduled ingress reaches the API-owned real child loop."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    app = create_api_app(project_root=tmp_path)
    route = "/v1/agent-schedules/hourly-report/evaluations"

    with TestClient(app) as client:
        admitted = client.post(
            route,
            headers=_headers(),
            json=_schedule_payload(evaluation_id="schedule-evaluation:e2e", include_prior=False),
        )
        assert admitted.status_code == 202
        wake_id = admitted.json()["wake"]["wake_id"]
        retained = _wait_for_completed_wake(client, wake_id)
        inspection = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    assert retained["state"] == "completed"
    assert retained["trigger"]["schedule_id"] == "hourly-report"
    assert inspection["wakes"][0]["source"] == "scheduled"
    assert inspection["wakes"][0]["trigger"] == retained["trigger"]
    assert inspection["schedule_evaluations"][0]["evaluation_id"] == "schedule-evaluation:e2e"
    assert app.state.api_runtime_context.active_background_task_count == 0


def test_api_owned_supervisor_dispatches_real_child_and_exposes_composed_inspection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. API wake reaches the real child/broker loop and durable inspector."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    app = create_api_app(project_root=tmp_path)

    with TestClient(app) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=_wake_payload())
        assert admitted.status_code == 202
        wake_id = admitted.json()["wake"]["wake_id"]
        retained = _wait_for_completed_wake(client, wake_id)
        inspection = client.get("/v1/agent-runs/run-1", headers=_headers())
        replay = client.get("/v1/agent-runs/run-1/replay", headers=_headers())

        assert retained["state"] == "completed"
        assert retained["result_ref"] == "agent-final-truth:run-1"
        assert inspection.status_code == 200
        body = inspection.json()
        assert body["run"]["lifecycle_state"] == "completed"
        assert len(body["iterations"]) == 2
        assert [wake["wake_id"] for wake in body["wakes"]] == [wake_id]
        assert body["operator_summary"]["stopped_because"] == "normal_execution"
        assert body["operator_summary"]["running"] is False
        assert replay.json()["status"] == "matched"
        existing = client.post(
            "/v1/agent-wakes",
            headers=_headers(),
            json=_wake_payload(occurrence_id="api-request-2", existing_run=True),
        )
        assert existing.status_code == 202
        existing_wake_id = existing.json()["wake"]["wake_id"]
        existing_retained = _wait_for_completed_wake(client, existing_wake_id)
        repeated_inspection = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        assert existing_retained["result_ref"] == "agent-final-truth:run-1"
        assert len(repeated_inspection["iterations"]) == 2
        assert {wake["wake_id"] for wake in repeated_inspection["wakes"]} == {wake_id, existing_wake_id}
        assert app.state.api_runtime_context.active_background_task_count >= 1

    assert app.state.api_runtime_context.closed is True
    assert app.state.api_runtime_context.active_background_task_count == 0


def test_api_owned_supervisor_prepares_approved_effect_and_resumes_real_child(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. A wake-fenced effect pause resumes only through authenticated approval."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    inputs.joinpath("tickets.json").write_text('{"source":"api-effect-fixture"}', encoding="utf-8")
    wake_payload = _effect_wake_payload()

    first_app = create_api_app(project_root=tmp_path)
    with TestClient(first_app) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=wake_payload)
        assert admitted.status_code == 202
        first_wake = _wait_for_completed_wake(client, admitted.json()["wake"]["wake_id"])
        blocked = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        assert not tmp_path.joinpath("reports", "ticket-report.json").exists()
        approval_id = blocked["approvals"][0]["request_id"]

    request = wake_payload["dispatch"]["request"]
    deadline = datetime.fromisoformat(request["deadline_utc"])
    resolution_payload = {
        "decision": "approved",
        "actor_ref": "operator:api-effect",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "next_lease_expires_at_utc": (deadline - timedelta(seconds=1)).isoformat(),
        "decision_timestamps_utc": [(deadline - timedelta(seconds=2)).isoformat()],
        "next_lease_expiries_utc": [],
    }
    _configure_api(monkeypatch, db_path, enabled=False)
    second_app = create_api_app(project_root=tmp_path)
    with TestClient(second_app) as client:
        resolution = client.post(
            f"/v1/agent-runs/run-1/effects/{approval_id}/resolve",
            headers=_headers(),
            json=resolution_payload,
        )
        assert resolution.status_code == 200
        resolution_body = resolution.json()
        repeated = client.post(
            f"/v1/agent-runs/run-1/effects/{approval_id}/resolve",
            headers=_headers(),
            json=resolution_payload,
        )
        still_blocked = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    _configure_api(monkeypatch, db_path, enabled=True)
    third_app = create_api_app(project_root=tmp_path)
    with TestClient(third_app) as client:
        second_wake = _wait_for_completed_wake(client, resolution_body["wake"]["wake_id"])
        completed = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    assert first_wake["state"] == "completed"
    assert blocked["run"]["lifecycle_state"] == "operator_blocked"
    assert [item["effect_id"] for item in blocked["effects"]] == ["agent-effect:read-ticket-source"]
    assert blocked["approvals"][0]["status"] == "pending"
    assert tmp_path.joinpath("reports", "ticket-report.json").is_file()
    assert resolution_body["status"] == "resume_queued"
    assert resolution_body["wake_status"] == "enqueued"
    assert repeated.json()["wake_status"] == "idempotent"
    assert still_blocked["run"]["lifecycle_state"] == "operator_blocked"
    assert second_wake["state"] == "completed"
    assert completed["run"]["lifecycle_state"] == "completed"
    assert len(completed["effects"]) == 2
    assert any(
        item["checkpoint"]["checkpoint_id"].startswith("agent-post-effects-checkpoint:")
        and item["acceptance"]["outcome"] == "checkpoint_accepted"
        for item in completed["checkpoints"]
    )
    assert any(item["result"] == "resume_authorized" for item in completed["operator_actions"])
    assert first_app.state.api_runtime_context.active_background_task_count == 0
    assert second_app.state.api_runtime_context.active_background_task_count == 0
    assert third_app.state.api_runtime_context.active_background_task_count == 0


def test_authenticated_effect_denial_closes_run_without_write_or_resume_wake(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. Public denial retains one paused wake and performs no proposed write."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    inputs.joinpath("tickets.json").write_text('{"source":"denial-fixture"}', encoding="utf-8")

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        admitted = client.post(
            "/v1/agent-wakes",
            headers=_headers(),
            json=_effect_wake_payload(),
        )
        first_wake = _wait_for_completed_wake(client, admitted.json()["wake"]["wake_id"])
        blocked = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        approval_id = blocked["approvals"][0]["request_id"]
        route = f"/v1/agent-runs/run-1/effects/{approval_id}/resolve"
        denial_payload = {
            "decision": "denied",
            "actor_ref": "operator:api-denial",
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }
        unauthorized = client.post(route, json=denial_payload)
        denied = client.post(route, headers=_headers(), json=denial_payload)
        inspection = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    assert unauthorized.status_code == 403
    assert denied.status_code == 200 and denied.json()["status"] == "denied"
    assert denied.json()["wake"] is None
    assert first_wake["state"] == "completed"
    assert inspection["run"]["lifecycle_state"] == "failed_terminal"
    assert len(inspection["wakes"]) == 1
    assert not tmp_path.joinpath("reports", "ticket-report.json").exists()


def test_observed_read_only_effect_can_resume_without_a_write_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. Safe read-only proposals use explicit continuation without a fake gate."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    inputs.joinpath("tickets.json").write_text('{"source":"read-only-fixture"}', encoding="utf-8")
    wake_payload = _effect_wake_payload(read_only=True)

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        admitted = client.post("/v1/agent-wakes", headers=_headers(), json=wake_payload)
        first_wake = _wait_for_completed_wake(client, admitted.json()["wake"]["wake_id"])
        blocked = client.get("/v1/agent-runs/run-1", headers=_headers()).json()
        deadline = datetime.fromisoformat(wake_payload["dispatch"]["request"]["deadline_utc"])
        resumed = client.post(
            "/v1/agent-runs/run-1/effects/resume",
            headers=_headers(),
            json={
                "actor_ref": "operator:read-only",
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "next_lease_expires_at_utc": (deadline - timedelta(seconds=1)).isoformat(),
                "decision_timestamps_utc": [(deadline - timedelta(seconds=2)).isoformat()],
                "next_lease_expiries_utc": [],
            },
        )
        second_wake = _wait_for_completed_wake(client, resumed.json()["wake"]["wake_id"])
        completed = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    assert first_wake["state"] == "completed"
    assert blocked["run"]["lifecycle_state"] == "operator_blocked"
    assert blocked["approvals"] == [] and len(blocked["effects"]) == 1
    assert resumed.status_code == 200 and resumed.json()["status"] == "resume_queued"
    assert resumed.json()["receipt"] is None and resumed.json()["operator_action"] is None
    assert second_wake["state"] == "completed"
    assert completed["run"]["lifecycle_state"] == "completed"
    assert not tmp_path.joinpath("reports", "ticket-report.json").exists()


def test_failed_wake_driven_read_enters_recovery_without_preparing_later_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. Read uncertainty fences later proposals and the claimed wake."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        admitted = client.post(
            "/v1/agent-wakes",
            headers=_headers(),
            json=_effect_wake_payload(),
        )
        wake = _wait_for_completed_wake(client, admitted.json()["wake"]["wake_id"])
        inspection = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    assert wake["state"] == "recovery_required" and wake["uncertainty"] is True
    assert inspection["run"]["lifecycle_state"] == "recovery_pending"
    assert len(inspection["effects"]) == 1
    assert inspection["effects"][0]["uncertainty_classification"] == "unresolved_residual_uncertainty"
    assert inspection["approvals"] == []
    assert not tmp_path.joinpath("reports", "ticket-report.json").exists()


def test_manual_cli_wake_is_consumed_by_api_owned_supervisor(tmp_path: Path, monkeypatch, capsys) -> None:
    """Layer: end-to-end. The public manual transport feeds the same production dispatcher as API ingress."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    payload = _wake_payload(occurrence_id="manual-cli-1")
    dispatch = payload["dispatch"]
    request_path = tmp_path / "manual-request.json"
    request_path.write_text(json.dumps(dispatch["request"]), encoding="utf-8")
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    args = [
        "agent", "wake", "enqueue", "--db", str(db_path),
        "--workload-id", str(payload["workload_id"]),
        "--occurrence-id", str(payload["occurrence_id"]),
        "--request", str(request_path),
        "--creation-timestamp-utc", str(dispatch["creation_timestamp_utc"]),
        "--json",
    ]
    for timestamp in dispatch["decision_timestamps_utc"]:
        args.extend(("--decision-timestamp-utc", str(timestamp)))
    for timestamp in dispatch["next_lease_expiries_utc"]:
        args.extend(("--next-lease-expires-at-utc", str(timestamp)))

    assert main(args) == 0
    admitted = json.loads(capsys.readouterr().out)
    app = create_api_app(project_root=tmp_path)
    with TestClient(app) as client:
        retained = _wait_for_completed_wake(client, admitted["wake"]["wake_id"])
        inspection = client.get("/v1/agent-runs/run-1", headers=_headers()).json()

    assert admitted["wake"]["source"] == "manual"
    assert retained["state"] == "completed"
    assert retained["result_ref"] == "agent-final-truth:run-1"
    assert [wake["source"] for wake in inspection["wakes"]] == ["manual"]
    assert app.state.api_runtime_context.active_background_task_count == 0


def _configure_api(monkeypatch, db_path: Path, *, enabled: bool) -> None:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_DB_PATH", str(db_path))
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_PROVIDER", "deterministic_fixture")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "1" if enabled else "0")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CLAIM_LEASE_SECONDS", "20")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_CLAIM_RENEWAL_SECONDS", "1")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_IDLE_WAIT_SECONDS", "0.02")


async def _claim_wake(db_path: Path) -> None:
    claim = await AsyncGovernedAgentWakeRepository(db_path).claim_next(
        owner_id="supervisor:test",
        now_utc="2026-09-07T11:59:58Z",
        lease_expires_at_utc="2026-09-07T12:01:00Z",
        max_active_claims=1,
    )
    assert claim.status == "claimed"


def _wake_payload(*, occurrence_id: str = "api-request-1", existing_run: bool = False) -> dict:
    now = datetime.now(UTC)
    request = agent_request()
    request["deadline_utc"] = (now + timedelta(seconds=20)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(seconds=18)).isoformat()
    payload = {
        "occurrence_id": occurrence_id,
        "target_kind": "existing_run" if existing_run else "new_run",
        "dispatch": {
            "schema_version": "governed_agent_wake_dispatch.v1",
            "request": request,
            "creation_timestamp_utc": now.isoformat(),
            "decision_timestamps_utc": [
                (now + timedelta(seconds=1)).isoformat(),
                (now + timedelta(seconds=2)).isoformat(),
            ],
            "next_lease_expiries_utc": [(now + timedelta(seconds=18)).isoformat()],
        },
    }
    if existing_run:
        payload["target_run_id"] = "run-1"
    else:
        payload["workload_id"] = "governed-agent-loop"
    return payload


def _effect_wake_payload(*, read_only: bool = False) -> dict:
    payload = _wake_payload(occurrence_id="api-effect-request-1")
    request = payload["dispatch"]["request"]
    request["namespace_scope"] = ["issue:issue-1"]
    request["admitted_capabilities"] = ["agent.iteration.v1", "read_file", "write_file"]
    request["extension_config"] = {
        "effect_demo": {
            "enabled": True,
            "namespace": "issue:issue-1",
            "read_path": "inputs/tickets.json",
            "write_path": "reports/ticket-report.json",
            "read_only": read_only,
        }
    }
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        budget = request[scope]
        budget["per_capability_effects"] = [
            {"capability": "read_file", "count": 1},
            {"capability": "write_file", "count": 1},
        ]
        budget["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in budget.items() if key != "snapshot_digest"}
        )
    return payload


def _schedule_payload(*, evaluation_id: str, include_prior: bool) -> dict:
    observed = datetime.now(UTC).replace(microsecond=0)
    dispatch = _wake_payload(occurrence_id=evaluation_id)["dispatch"]
    local_times = [observed]
    if include_prior:
        local_times.insert(0, observed - timedelta(minutes=5))
    return {
        "evaluation_id": evaluation_id,
        "timezone": "UTC",
        "observed_at_utc": observed.isoformat(),
        "misfire_grace_seconds": 0,
        "missed_policy": "fire_once",
        "coalescing_policy": "latest",
        "occurrences": [
            {
                "scheduled_for_local": local.replace(tzinfo=None).isoformat(),
                "fold": 0,
                "target_kind": "new_run",
                "workload_id": "governed-agent-loop",
                "dispatch": dispatch,
            }
            for local in local_times
        ],
    }


def _write_catalog(tmp_path: Path) -> Path:
    template_root = Path("docs/templates/governed_agent_external").resolve()
    manifest_path = template_root / "extension.yaml"
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
                        "source": "test-fixture",
                        "path": str(template_root),
                        "contract_style": "sdk_v0",
                        "manifest_path": str(manifest_path),
                        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"],
                        "manifest_entries": manifest["workloads"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return catalog_path


def _wait_for_completed_wake(client: TestClient, wake_id: str) -> dict:
    for _ in range(100):
        response = client.get(f"/v1/agent-wakes/{wake_id}", headers=_headers())
        assert response.status_code == 200
        wake = response.json()
        if wake["state"] in {"completed", "recovery_required", "cancelled"}:
            return wake
        time.sleep(0.05)
    raise AssertionError("governed-agent wake did not reach a terminal queue state")


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-key"}
