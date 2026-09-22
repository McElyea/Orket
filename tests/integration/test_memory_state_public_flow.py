"""Layer: integration. Authenticated application API, SDK bridge and actual SQLite restart."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from orket.application.services.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.interfaces.api import create_api_app
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest

pytestmark = pytest.mark.integration


def test_sdk_and_application_api_share_corrected_namespaced_fact_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "memory-fixture-key")
    path = tmp_path / ".orket/durable/db/extension_runtime_memory.db"
    provider = SQLiteMemoryCapabilityProvider(path, extension_id="memory-fixture")
    initial = provider.write(MemoryWriteRequest(scope="profile_memory", key="user_fact.name", value="Aster",
        metadata={"user_confirmed": True, "observed_at": "2030-01-01T00:00:00Z"}))
    assert initial.ok
    route = "/v1/extensions/memory-fixture/runtime/memory/"
    headers = {"X-API-Key": "memory-fixture-key"}
    payload = dict(scope="profile_memory", key="user_fact.name", value="Nova",
        metadata={"user_confirmed": True, "observed_at": "2030-01-02T00:00:00Z"})
    with TestClient(create_api_app(project_root=tmp_path)) as client:
        refusal = client.post(route + "write", headers=headers, json=payload)
        assert refusal.status_code == 400
        assert "E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION" in refusal.text
        payload["metadata"]["user_correction"] = True
        corrected = client.post(route + "write", headers=headers, json=payload)
        assert corrected.status_code == 200 and corrected.json()["record"]["value"] == "Nova"
        payload["metadata"]["observed_at"] = "2029-01-01T00:00:00Z"
        stale = client.post(route + "write", headers=headers, json=payload)
        assert stale.status_code == 400 and "E_PROFILE_MEMORY_STALE_UPDATE" in stale.text
    with TestClient(create_api_app(project_root=tmp_path)) as restarted:
        query = restarted.post(route + "query", headers=headers,
            json=dict(scope="profile_memory", query="key:user_fact.name", limit=10))
        assert query.status_code == 200
        record, = query.json()["records"]
        assert record["value"] == "Nova" and record["metadata"]["conflict_resolution"] == "user_correction"
    query = MemoryQueryRequest(scope="profile_memory", query="key:user_fact.name", limit=10)
    assert provider.query(query).records[0].value == "Nova"
    other = SQLiteMemoryCapabilityProvider(path, extension_id="other-fixture")
    assert other.query(query).records == []
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT memory_key, memory_value FROM extension_memory").fetchall() == [
            ("ext:memory-fixture:user_fact.name", "Nova")]
