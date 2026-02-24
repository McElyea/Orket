from __future__ import annotations

from fastapi.testclient import TestClient

from orket.interfaces.api import app
import orket.interfaces.api as api_module


client = TestClient(app)


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
