"""Real read failures, policy rotation and staging effects under captured policy inputs."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import orket.application.services.kernel_capability_policy_service as service
from orket.core.contracts.kernel_capability_policy import KernelCapabilityPolicy
from orket.kernel.v1 import api
from tests.helpers.kernel_capability_probe import policy_payload, turn_request

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mode", ["disabled", "no-tool-call"])
def test_turn_without_policy_evaluation_retains_staging(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(service, "DEFAULT_KERNEL_CAPABILITY_POLICY_PATH", tmp_path / "absent.json")
    root = tmp_path / "effect"
    request = turn_request(root)
    if mode == "disabled":
        request["turn_input"]["context"]["capability_enforcement"] = False
    else:
        del request["turn_input"]["tool_call"]
    result = api.execute_turn(request)
    assert result["outcome"] == "PASS"
    assert list(root.rglob("fixture.json"))


@pytest.mark.parametrize(
    "kind,error",
    [
        ("missing", FileNotFoundError),
        ("malformed", json.JSONDecodeError),
        ("scalar", ValueError),
        ("shape", ValueError),
        ("directory", OSError),
        ("encoding", UnicodeDecodeError),
    ],
)
@pytest.mark.parametrize("operation", ["resolve", "authorize", "execute"])
def test_unreadable_or_invalid_policy_refuses_before_local_effects(tmp_path, monkeypatch, kind, error, operation):
    path = tmp_path / "selected.json"
    if kind == "directory":
        path.mkdir()
    elif kind != "missing":
        path.write_bytes({"malformed": b"{", "scalar": b"null", "shape": b"{}", "encoding": b"\xff"}[kind])
    monkeypatch.setattr(service, "DEFAULT_KERNEL_CAPABILITY_POLICY_PATH", path)
    root = tmp_path / "effect"
    operations = {
        "resolve": (api.resolve_capability, {"contract_version": "kernel_api/v1", "role": "coder", "task": "edit"}),
        "authorize": (
            api.authorize_tool_call,
            {"contract_version": "kernel_api/v1", "context": {}, "tool_request": {}},
        ),
        "execute": (api.execute_turn, turn_request(root)),
    }
    function, request = operations[operation]
    with pytest.raises(error):
        function(request)
    assert not root.exists()


def test_real_policy_rotation_changes_next_call_without_mutating_prior_snapshot(tmp_path):
    path = tmp_path / "selected.json"
    path.write_text(json.dumps(policy_payload()), encoding="utf-8")
    granted = service.capture_kernel_capability_policy(policy_path=path)
    path.write_text(json.dumps(policy_payload([])), encoding="utf-8")
    denied = service.capture_kernel_capability_policy(policy_path=path)
    result = api.execute_turn(turn_request(tmp_path / "denied"), policy_inputs=denied)
    assert result["outcome"] == "FAIL" and not (tmp_path / "denied").exists()
    first = api.execute_turn(turn_request(tmp_path / "granted"), policy_inputs=granted)
    assert first["outcome"] == "PASS"
    assert list((tmp_path / "granted").rglob("fixture.json"))
    assert first == api.execute_turn(turn_request(tmp_path / "repeat"), policy_inputs=granted)


@pytest.mark.parametrize("operation", ["resolve", "authorize", "execute"])
def test_borrowed_request_detached_before_one_actual_policy_read(tmp_path, monkeypatch, operation):
    path = tmp_path / "selected.json"
    path.write_text(json.dumps(policy_payload()), encoding="utf-8")
    monkeypatch.setattr(service, "DEFAULT_KERNEL_CAPABILITY_POLICY_PATH", path)
    entered, release = threading.Event(), threading.Event()
    read, observed = service.read_kernel_capability_policy, []

    def held(selected):
        observed.append(selected)
        payload = read(selected)
        entered.set()
        assert release.wait(10), "policy read was not released"
        return payload

    monkeypatch.setattr(service, "read_kernel_capability_policy", held)
    request = turn_request(tmp_path / "actual")
    if operation == "resolve":
        request = {"contract_version": "kernel_api/v1", "role": "coder", "task": "edit", "context": {}}
    elif operation == "authorize":
        request = {"contract_version": "kernel_api/v1", **request["turn_input"]}
        request["tool_request"] = request.pop("tool_call")
    function = {"resolve": api.resolve_capability, "authorize": api.authorize_tool_call, "execute": api.execute_turn}[
        operation
    ]
    original = json.loads(json.dumps(request))
    expected = function(original, policy_inputs=KernelCapabilityPolicy.from_payload(policy_payload()))
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(function, request)
        try:
            assert entered.wait(10)
            context = request["turn_input"]["context"] if operation == "execute" else request["context"]
            context["permissions"] = ["foreign.execute"]
            if operation == "execute":
                request["turn_input"]["stage_triplet"]["body"]["value"] = "borrowed-after-read"
            request.clear()
            path.write_text(json.dumps(policy_payload([])), encoding="utf-8")
            release.set()
            assert pending.result(timeout=10) == expected
            assert observed == [path.absolute()]
        finally:
            release.set()
    if operation == "execute":
        assert list((tmp_path / "actual").rglob("fixture.json"))
        assert all(
            b"borrowed-after-read" not in path.read_bytes()
            for path in (tmp_path / "actual").rglob("*")
            if path.is_file()
        )
