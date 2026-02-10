import pytest
from fastapi.testclient import TestClient
from orket.interfaces.api import app
import os

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "organization": "Orket"}

def test_version_unauthenticated():
    # If ORKET_API_KEY is not set, it might pass or fail depending on env
    # For testing, we assume auth is required if the key is present
    response = client.get("/v1/version")
    if os.getenv("ORKET_API_KEY"):
        assert response.status_code == 403
    else:
        assert response.status_code == 200

def test_version_authenticated(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/version", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert "version" in response.json()

def test_heartbeat():
    response = client.get("/v1/system/heartbeat")
    # Heartbeat might be under v1_router which requires auth if configured
    if response.status_code == 403:
        response = client.get("/v1/system/heartbeat", headers={"X-API-Key": os.getenv("ORKET_API_KEY", "")})
    
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "online"
        assert "timestamp" in data

def test_explorer_security(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    # Try to escape PROJECT_ROOT
    response = client.get("/v1/system/explorer?path=../../", headers={"X-API-Key": "test-key"})
    assert response.status_code == 403

def test_read_security(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    # Try to read something sensitive outside root
    response = client.get("/v1/system/read?path=../../etc/passwd", headers={"X-API-Key": "test-key"})
    assert response.status_code == 403

def test_calendar():
    # Public or private? api.py says it's in v1_router
    headers = {"X-API-Key": os.getenv("ORKET_API_KEY", "")}
    response = client.get("/v1/system/calendar", headers=headers)
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert "current_sprint" in data
        assert "sprint_start" in data

def test_metrics():
    headers = {"X-API-Key": os.getenv("ORKET_API_KEY", "")}
    response = client.get("/v1/system/metrics", headers=headers)
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
