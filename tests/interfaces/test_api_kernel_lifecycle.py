from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from orket.interfaces.api import app
import orket.interfaces.api as api_module


client = TestClient(app)


def _load_schema(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_registry(root_schema: dict) -> Registry:
    schema_paths = [
        "docs/projects/OS/contracts/replay-report.schema.json",
        "docs/projects/OS/contracts/kernel-issue.schema.json",
    ]
    registry = Registry().with_resource(root_schema["$id"], Resource.from_contents(root_schema))
    for path in schema_paths:
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


def test_kernel_lifecycle_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_kernel_run_lifecycle(*, workflow_id, execute_turn_requests, finish_outcome="PASS", start_request=None):
        captured["workflow_id"] = workflow_id
        captured["execute_turn_requests"] = execute_turn_requests
        captured["finish_outcome"] = finish_outcome
        captured["start_request"] = start_request
        return {"ok": True, "workflow_id": workflow_id}

    monkeypatch.setattr(api_module.engine, "kernel_run_lifecycle", fake_kernel_run_lifecycle)

    response = client.post(
        "/v1/kernel/lifecycle",
        headers={"X-API-Key": "test-key"},
        json={
            "workflow_id": "wf-api-kernel",
            "execute_turn_requests": [{"turn_id": "turn-0001", "turn_input": {}, "commit_intent": "stage_only"}],
            "finish_outcome": "PASS",
            "start_request": {"visibility_mode": "local_only"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "workflow_id": "wf-api-kernel"}
    assert captured["workflow_id"] == "wf-api-kernel"
    assert captured["execute_turn_requests"][0]["turn_id"] == "turn-0001"


def test_kernel_compare_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_kernel_compare_runs(request):
        captured["request"] = request
        return {"outcome": "FAIL", "issues": [{"code": "E_REPLAY_EQUIVALENCE_FAILED"}]}

    monkeypatch.setattr(api_module.engine, "kernel_compare_runs", fake_kernel_compare_runs)

    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {"run_id": "run-a"},
            "run_b": {"run_id": "run-b"},
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "FAIL"
    assert response.json()["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert captured["request"]["contract_version"] == "kernel_api/v1"
    assert captured["request"]["run_a"]["run_id"] == "run-a"


def test_kernel_replay_endpoint_routes_to_engine_and_propagates_failure_codes(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    def fake_kernel_replay_run(request):
        descriptor = request.get("run_descriptor", {})
        if "workflow_id" not in descriptor:
            return {"outcome": "FAIL", "issues": [{"code": "E_REPLAY_INPUT_MISSING"}]}
        if descriptor.get("contract_version") != "kernel_api/v1":
            return {"outcome": "FAIL", "issues": [{"code": "E_REPLAY_VERSION_MISMATCH"}]}
        return {"outcome": "PASS", "issues": []}

    monkeypatch.setattr(api_module.engine, "kernel_replay_run", fake_kernel_replay_run)

    missing = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={"run_descriptor": {"run_id": "run-r1"}},
    )
    assert missing.status_code == 200
    assert missing.json()["issues"][0]["code"] == "E_REPLAY_INPUT_MISSING"

    mismatch = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={
            "run_descriptor": {
                "run_id": "run-r2",
                "workflow_id": "wf-r2",
                "contract_version": "kernel_api/v0",
                "schema_version": "v1",
            }
        },
    )
    assert mismatch.status_code == 200
    assert mismatch.json()["issues"][0]["code"] == "E_REPLAY_VERSION_MISMATCH"


def test_kernel_replay_endpoint_real_engine_success_with_full_descriptor(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={
            "run_descriptor": {
                "run_id": "run-r3",
                "workflow_id": "wf-r3",
                "policy_profile_ref": "policy:v1",
                "model_profile_ref": "model:v1",
                "runtime_profile_ref": "runtime:v1",
                "trace_ref": "trace://run-r3",
                "state_ref": "state://run-r3",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "PASS"
    assert payload["mode"] == "replay_run"
    schema = _load_schema("docs/projects/OS/contracts/replay-report.schema.json")
    registry = _build_registry(schema)
    Draft202012Validator(schema, registry=registry).validate(payload)


def test_kernel_replay_endpoint_real_engine_fail_payload_conforms_schema(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={"run_descriptor": {"run_id": "run-r4"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_INPUT_MISSING"
    schema = _load_schema("docs/projects/OS/contracts/replay-report.schema.json")
    registry = _build_registry(schema)
    Draft202012Validator(schema, registry=registry).validate(payload)


def test_kernel_compare_endpoint_real_engine_detects_pointer_drift(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "orphan",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/1",
                        "message": "orphan",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert payload["issues"][0]["details"]["mismatch_fields"] == ["issue_codes"]


def test_kernel_compare_endpoint_real_engine_contract_version_drift(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v0",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [],
                "events": [],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert payload["issues"][0]["details"]["mismatch_fields"] == ["contract_version"]


def test_kernel_compare_endpoint_real_engine_pointer_and_stage_drift_ordering(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "x",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "FAIL"}],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/1",
                        "message": "y",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert payload["issues"][0]["details"]["mismatch_fields"] == ["issue_codes", "stage_outcomes"]


def test_kernel_compare_endpoint_real_engine_passes_mixed_order_normalization(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "promotion",
                        "code": "E_PROMOTION_OUT_OF_ORDER",
                        "location": "/turns/2",
                        "message": "x",
                        "details": {},
                    },
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "y",
                        "details": {},
                    },
                ],
                "events": [
                    "[INFO] [STAGE:promotion] [CODE:I_NOOP_PROMOTION] [LOC:/turn-0002] noop |",
                    "[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] pass |",
                ],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "different",
                        "details": {},
                    },
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "promotion",
                        "code": "E_PROMOTION_OUT_OF_ORDER",
                        "location": "/turns/2",
                        "message": "different",
                        "details": {},
                    },
                ],
                "events": [
                    "[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] pass alt |",
                    "[INFO] [STAGE:promotion] [CODE:I_NOOP_PROMOTION] [LOC:/turn-0002] noop alt |",
                ],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "PASS"


def test_kernel_compare_endpoint_response_conforms_to_replay_report_schema(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {"run_id": "run-a", "contract_version": "kernel_api/v1", "schema_version": "v1", "turn_digests": [], "stage_outcomes": [], "issues": [], "events": []},
            "run_b": {"run_id": "run-b", "contract_version": "kernel_api/v1", "schema_version": "v1", "turn_digests": [], "stage_outcomes": [], "issues": [], "events": []},
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    schema = _load_schema("docs/projects/OS/contracts/replay-report.schema.json")
    registry = _build_registry(schema)
    Draft202012Validator(schema, registry=registry).validate(response.json())


def test_kernel_compare_endpoint_malformed_payload_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {"run_id": "run-a"},
            "compare_mode": "structural_parity"
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"][0]["loc"][-1] == "run_b"


def test_kernel_compare_endpoint_realistic_artifact_fixture(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    fixture_path = Path("tests/interfaces/fixtures/kernel_compare_realistic_fixture.json")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": fixture["run_a"],
            "run_b": fixture["run_b"],
            "compare_mode": fixture["compare_mode"],
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == fixture["expect_outcome"]
