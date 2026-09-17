"""Public API serialization retains the SDK's latency availability contract."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.capabilities.sdk_static_provider import StaticLLMCapabilityProvider
from orket.interfaces.routers.extension_runtime import build_extension_runtime_router


# Layer: integration
def test_extension_generate_route_retains_unavailable_latency(tmp_path: Path):
    service = ExtensionRuntimeService(project_root=tmp_path,model_provider=StaticLLMCapabilityProvider(text="fixture answer"))
    app = FastAPI()
    app.include_router(build_extension_runtime_router(service_getter=lambda:service),prefix="/v1")
    with TestClient(app) as client:
        response = client.post("/v1/extensions/orket.timing/runtime/llm/generate",
                               json={"system_prompt":"","user_message":"fixture question"})
    assert response.status_code == 200
    assert response.json()["text"] == "fixture answer"
    assert response.json()["latency_ms"] is None
    assert response.json()["latency_posture"] == "unavailable"
    assert response.json()["schema_version"] == "model_generate_response.v1"
