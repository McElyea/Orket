"""Synthetic evidence controls; these do not establish native Mac or Metal execution."""
import json
from types import SimpleNamespace

import pytest

from scripts.ci.candidate_install_support import file_identity, require_missing_provider_refusal
from scripts.ci.macos_acceptance_evidence import (
    CASE_IDS,
    metal_log_observation,
    read_verified_receipt,
    required_case_verdict,
)
from scripts.ci.verify_macos_acceptance import finish_verdict

pytestmark = pytest.mark.contract


def missing_provider_evidence():
    endpoint = "http://127.0.0.1:43210/v1"
    return {"project": "synthetic project", "missing_provider_endpoint": endpoint, "missing_provider": {
        "project": "synthetic project", "provider": "llama_cpp", "model": "acceptance-model", "base_url": endpoint,
        "ok": False, "observed_path": "primary", "observed_result": "failure",
        "provider_observation": {"catalog_admitted": False, "resources_closed": True, "inference": "not_established",
            "error": "ModelConnectionError: Provider runtime preparation failed provider=llama_cpp "
                     "requested_model=acceptance-model: All connection attempts failed"},
        "command_observation": {"ok": True, "returncode": 0, "reason": "completed",
                                "cleanup_confirmed": True, "capture_complete": True}}}


@pytest.mark.parametrize("scope,field,value", [
    ("provider_observation", "error", "ValueError: timeout must be greater than or equal to connect_timeout_seconds"),
    ("provider_observation", "error", "ModelConnectionError: invalid model catalog"),
    ("provider_observation", "error", "ModelConnectionError: HTTP 401 Unauthorized"),
    ("provider_observation", "resources_closed", False),
    ("provider_observation", "catalog_admitted", True),
    ("provider_observation", "inference", "success"),
    ("command_observation", "ok", False),
    ("command_observation", "returncode", 1),
    ("command_observation", "reason", "timeout"),
    ("command_observation", "cleanup_confirmed", False),
    ("command_observation", "capture_complete", False),
    (None, "ok", True),
    (None, "provider", "ollama"),
    (None, "model", "another-model"),
    (None, "project", "another project"),
    (None, "base_url", "http://127.0.0.1:43211/v1"),
    (None, "observed_path", "blocked"),
    (None, "observed_result", "environment blocker"),
])
def test_unrelated_diagnostic_failures_cannot_prove_missing_provider(scope, field, value):
    setup = missing_provider_evidence()
    require_missing_provider_refusal(setup)
    diagnostic = setup["missing_provider"]
    (diagnostic[scope] if scope else diagnostic)[field] = value
    with pytest.raises(ValueError, match="connection failure"):
        require_missing_provider_refusal(setup)


@pytest.mark.parametrize("endpoint", ["http://example.com:1234/v1", "http://127.0.0.1/v1",
                                    "http://user:secret@127.0.0.1:1234/v1", "http://127.0.0.1:1234/other"])
def test_missing_provider_control_requires_its_held_loopback_endpoint(endpoint):
    setup = missing_provider_evidence()
    setup["missing_provider_endpoint"] = setup["missing_provider"]["base_url"] = endpoint
    with pytest.raises(ValueError, match="connection failure"):
        require_missing_provider_refusal(setup)


def cases():
    return {key: {"status": "PASS", "evidence": {"synthetic": True}} for key in CASE_IDS}


@pytest.mark.parametrize("identity", CASE_IDS)
@pytest.mark.parametrize("fault", ["missing", "FAIL", "BLOCKED", "SKIP", "empty-evidence"])
def test_every_case_requires_success_and_evidence(identity, fault):
    rows = cases()
    if fault == "missing":
        del rows[identity]
    elif fault == "empty-evidence":
        rows[identity]["evidence"] = {}
    else:
        rows[identity]["status"] = fault
    assert not required_case_verdict(rows, native_mac=True)["macos_acceptance_complete"]


def test_extra_cases_and_windows_success_cannot_establish_mac_acceptance():
    rows = cases()
    assert required_case_verdict(rows, native_mac=True)["macos_acceptance_complete"]
    assert not required_case_verdict(rows, native_mac=False)["macos_acceptance_complete"]
    rows["additional"] = rows["MA-01"]
    assert not required_case_verdict(rows, native_mac=True)["macos_acceptance_complete"]


def test_explicit_windows_control_keeps_metal_blocked_and_mac_completion_false():
    rows = cases()
    rows["MA-05"]["status"] = "BLOCKED"
    run = SimpleNamespace(payload={"cases": rows, "native_mac": False, "windows_control": True})
    finish_verdict(run)
    assert run.payload["status"] == "CONTROL_PASS"
    assert run.payload["observed_result"] == "partial success"
    assert not run.payload["macos_acceptance_complete"]
    rows["MA-07"]["status"] = "BLOCKED"
    with pytest.raises(ValueError, match="All nine"):
        finish_verdict(run)


@pytest.mark.parametrize("fault", ["detection-only", "cpu-buffer", "zero-layers", "zero-buffer", "different-device"])
def test_metal_detection_or_cpu_execution_cannot_satisfy_allocation(fault):
    device = "llama_prepare_model_devices: using device Metal0 (Apple M4 Pro) (0000) - 12000 MiB free\n"
    layers = "llama_model_load: offloaded 33/33 layers to GPU\n"
    buffer = "llama_model_load: Metal0 model buffer size = 12345.25 MiB\n"
    if fault == "detection-only":
        layers, buffer = "", ""
    elif fault == "cpu-buffer":
        buffer = buffer.replace("Metal0", "CPU")
    elif fault == "different-device":
        buffer = buffer.replace("Metal0", "Metal1")
    elif fault == "zero-layers":
        layers = layers.replace("33/33", "0/33")
    else:
        buffer = buffer.replace("12345.25", "0.00")
    assert not metal_log_observation(device + layers + buffer)["metal_model_allocation_observed"]


def test_positive_metal_log_pattern_retains_its_inference_proof_limit():
    observed = metal_log_observation("using device Metal0 (Apple M4 Pro)\n"
                                    "offloaded 33/33 layers to GPU\nMetal0 model buffer size = 123.5 MiB")
    assert observed["metal_model_allocation_observed"]
    assert "Requires successful inference" in observed["claim_limit"]


@pytest.mark.parametrize("fault", ["status", "source", "exit", "reason", "cleanup", "capture", "log", "commands"])
def test_component_receipts_refuse_failed_or_changed_retained_evidence(tmp_path, fault):
    log = tmp_path / "synthetic.log"
    log.write_text("controlled receipt", encoding="utf-8")
    command = {"status": "PASS", "returncode": 0, "expected_exit": 0,
               "lifetime": {"reason": "completed", "cleanup_confirmed": True, "capture_complete": True},
               "stdout": file_identity(log), "stderr": file_identity(log)}
    payload = {"status": "PASS", "source_unchanged": True, "commands": [command]}
    receipt = tmp_path / "synthetic-receipt.json"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    assert read_verified_receipt(receipt) == payload
    if fault == "status":
        payload["status"] = "FAIL"
    elif fault == "source":
        payload["source_unchanged"] = False
    elif fault == "exit":
        command["returncode"] = 1
    elif fault == "reason":
        command["lifetime"]["reason"] = "timeout"
    elif fault in {"cleanup", "capture"}:
        command["lifetime"]["cleanup_confirmed" if fault == "cleanup" else "capture_complete"] = False
    elif fault == "commands":
        payload["commands"] = []
    else:
        log.write_text("changed log bytes", encoding="utf-8")
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        read_verified_receipt(receipt)
