# Layer: integration and end-to-end

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from orket.application.services.governed_agent_webhook_ingress_service import (
    governed_agent_webhook_signature,
)
from orket.interfaces.api import create_api_app
from tests.runtime.governed_agent_test_support import agent_request

_ISSUER = "integration-fixture"
_KEY_ID = "key-test-1"
_SECRET = "test-only-webhook-secret"


def test_webhook_api_enforces_both_auth_boundaries_and_survives_restart(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: integration. API and HMAC auth precede durable replay-safe admission."""
    db_path = tmp_path / "agent.sqlite3"
    _configure_api(monkeypatch, db_path, enabled=False)
    timestamp = _now_text()
    body = _body()
    route = f"/v1/agent-webhooks/{_ISSUER}/deliveries/delivery-1"
    signed_headers = _headers(body, timestamp=timestamp)

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        unauthorized_api = client.post(route, content=body, headers={
            key: value for key, value in signed_headers.items() if key != "X-API-Key"
        })
        unauthorized_hmac = client.post(
            route,
            content=body,
            headers={**signed_headers, "X-Orket-Webhook-Signature": "sha256=" + "0" * 64},
        )
        admitted = client.post(route, content=body, headers=signed_headers)
        replayed = client.post(route, content=body, headers=signed_headers)
        changed_body = _body(workload_id="different-workload")
        contradicted = client.post(
            route,
            content=changed_body,
            headers=_headers(changed_body, timestamp=timestamp),
        )

    assert unauthorized_api.status_code == 403
    assert unauthorized_hmac.status_code == 401
    assert admitted.status_code == 202 and admitted.json()["status"] == "enqueued"
    assert replayed.status_code == 202 and replayed.json()["status"] == "idempotent"
    assert contradicted.status_code == 409
    wake = admitted.json()["wake"]
    delivery = admitted.json()["delivery"]
    assert wake["source"] == "webhook"
    assert wake["trigger"]["delivery_ref"] == delivery["delivery_ref"]
    assert wake["trigger"]["content_digest"] == delivery["content_digest"]
    assert _SECRET not in json.dumps(admitted.json(), sort_keys=True)
    assert signed_headers["X-Orket-Webhook-Signature"] not in json.dumps(admitted.json(), sort_keys=True)

    with TestClient(create_api_app(project_root=tmp_path)) as client:
        listed = client.get(
            f"/v1/agent-webhooks/{_ISSUER}/deliveries",
            headers={"X-API-Key": "test-key"},
        )
        retained = client.get(f"/v1/agent-wakes/{wake['wake_id']}", headers={"X-API-Key": "test-key"})
        runtime = client.get("/v1/agent-runtime/status", headers={"X-API-Key": "test-key"})

    assert listed.status_code == 200 and listed.json()["items"] == [delivery]
    assert retained.status_code == 200 and retained.json()["trigger"] == wake["trigger"]
    assert runtime.json()["webhook_ingress_configured"] is True


def test_webhook_api_rejects_stale_delivery_and_incomplete_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: integration. Freshness and composition configuration fail closed."""
    db_path = tmp_path / "agent.sqlite3"
    _configure_api(monkeypatch, db_path, enabled=False)
    stale = (datetime.now(UTC) - timedelta(minutes=6)).isoformat(timespec="microseconds").replace("+00:00", "Z")
    body = _body()
    route = f"/v1/agent-webhooks/{_ISSUER}/deliveries/delivery-stale"
    with TestClient(create_api_app(project_root=tmp_path)) as client:
        response = client.post(route, content=body, headers=_headers(body, timestamp=stale, delivery_id="delivery-stale"))
        oversized_body = b"x" * 1_048_577
        oversized = client.post(
            f"/v1/agent-webhooks/{_ISSUER}/deliveries/delivery-oversized",
            content=oversized_body,
            headers=_headers(oversized_body, timestamp=_now_text(), delivery_id="delivery-oversized"),
        )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "E_AGENT_WEBHOOK_TIMESTAMP_EXPIRED"
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "E_AGENT_WEBHOOK_BODY_TOO_LARGE"

    monkeypatch.delenv("ORKET_GOVERNED_AGENT_WEBHOOK_SECRET")
    with pytest.raises(ValueError, match="E_AGENT_WEBHOOK_CONFIGURATION_INCOMPLETE"), TestClient(
        create_api_app(project_root=tmp_path)
    ):
        pass


def test_api_owned_supervisor_dispatches_authenticated_webhook_wake(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: end-to-end. Signed webhook ingress reaches the API-owned real child loop."""
    db_path = tmp_path / "agent.sqlite3"
    catalog_path = _write_catalog(tmp_path)
    _configure_api(monkeypatch, db_path, enabled=True)
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    app = create_api_app(project_root=tmp_path)
    timestamp = _now_text()
    body = _body()
    route = f"/v1/agent-webhooks/{_ISSUER}/deliveries/delivery-e2e"

    with TestClient(app) as client:
        admitted = client.post(
            route,
            content=body,
            headers=_headers(body, timestamp=timestamp, delivery_id="delivery-e2e"),
        )
        assert admitted.status_code == 202
        wake_id = admitted.json()["wake"]["wake_id"]
        retained = _wait_for_completed_wake(client, wake_id)
        inspection = client.get("/v1/agent-runs/run-1", headers={"X-API-Key": "test-key"}).json()

    assert retained["state"] == "completed"
    assert retained["trigger"]["delivery_id"] == "delivery-e2e"
    assert inspection["wakes"][0]["source"] == "webhook"
    assert inspection["webhook_deliveries"][0]["delivery_id"] == "delivery-e2e"
    assert inspection["webhook_deliveries"][0]["resulting_wake_id"] == wake_id
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
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_WEBHOOK_ISSUER_REF", _ISSUER)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_WEBHOOK_KEY_ID", _KEY_ID)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_WEBHOOK_SECRET", _SECRET)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_WEBHOOK_REPLAY_WINDOW_SECONDS", "300")


def _body(*, workload_id: str = "governed-agent-loop") -> bytes:
    now = datetime.now(UTC)
    request = agent_request()
    request["deadline_utc"] = (now + timedelta(seconds=20)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(seconds=18)).isoformat()
    payload = {
        "target_kind": "new_run",
        "workload_id": workload_id,
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
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _headers(body: bytes, *, timestamp: str, delivery_id: str = "delivery-1") -> dict[str, str]:
    return {
        "X-API-Key": "test-key",
        "Content-Type": "application/json",
        "X-Orket-Webhook-Timestamp": timestamp,
        "X-Orket-Webhook-Key-Id": _KEY_ID,
        "X-Orket-Webhook-Signature": governed_agent_webhook_signature(
            secret=_SECRET,
            issuer_ref=_ISSUER,
            delivery_id=delivery_id,
            delivered_at_utc=timestamp,
            body=body,
        ),
    }


def _now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_catalog(tmp_path: Path) -> Path:
    template_root = Path("docs/templates/governed_agent_external").resolve()
    manifest_path = template_root / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog_path = tmp_path / "extensions.json"
    catalog_path.write_text(json.dumps({"extensions": [{
        "extension_id": manifest["extension_id"],
        "extension_version": manifest["extension_version"],
        "extension_api_version": "1.0.0",
        "source": "test-fixture",
        "path": str(template_root),
        "contract_style": "sdk_v0",
        "manifest_path": str(manifest_path),
        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"],
        "manifest_entries": manifest["workloads"],
    }]}), encoding="utf-8")
    return catalog_path


def _wait_for_completed_wake(client: TestClient, wake_id: str) -> dict:
    for _ in range(100):
        response = client.get(f"/v1/agent-wakes/{wake_id}", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        wake = response.json()
        if wake["state"] in {"completed", "recovery_required", "cancelled"}:
            return wake
        time.sleep(0.05)
    raise AssertionError("governed-agent webhook wake did not reach a terminal queue state")
