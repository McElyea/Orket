"""Required-case verdicts and retained evidence admission for native Mac acceptance."""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.ci.candidate_install_support import file_identity, observe_quickstart, require_missing_provider_refusal
from scripts.ci.installed_process_controls import process_test_verdict

CASE_IDS = tuple(f"MA-{number:02d}" for number in range(1, 10))


def required_case_verdict(cases: dict, *, native_mac: bool) -> dict:
    complete = set(cases) == set(CASE_IDS) and all(
        cases[key].get("status") == "PASS" and cases[key].get("evidence") for key in CASE_IDS)
    return {"macos_acceptance_complete": bool(native_mac and complete),
            "all_cases_succeeded": bool(complete), "native_mac": native_mac}


def check_file(record: dict) -> None:
    if file_identity(Path(record["path"])) != {"path": record["path"], "sha256": record["sha256"]}:
        raise ValueError(f"Retained file changed: {record['path']}")


def read_verified_receipt(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "PASS" or value.get("source_unchanged") is not True or not value.get("commands"):
        raise ValueError(f"Passing source-bound component receipt required: {path}")
    for command in value["commands"]:
        lifetime = command["lifetime"]
        if (command["status"] != "PASS" or command["returncode"] != command["expected_exit"]
                or lifetime["reason"] != "completed" or not lifetime["cleanup_confirmed"] or not lifetime["capture_complete"]):
            raise ValueError("Component command lacks successful native settlement")
        check_file(command["stdout"])
        check_file(command["stderr"])
    return value


def admit_components(run, package_path: Path, process_path: Path) -> tuple[dict, dict]:
    package, process = read_verified_receipt(package_path), read_verified_receipt(process_path)
    for field in ("system", "machine", "release", "python"):
        if process["environment"][field] != run.payload["environment"][field]:
            raise ValueError("Process receipt belongs to a different platform configuration")
    if process["wheels"] != package["wheels"] or process["candidate_source"] != package["source"]:
        raise ValueError("Process evidence identifies a different candidate")
    if process["observations"]["installed"] != package["observations"]["installed"]:
        raise ValueError("Component installed interpreter/origin observations differ")
    for item in process["harness_files"]:
        check_file(item)
        if "source" in item and file_identity(run.repo / item["source"])["sha256"] != item["sha256"]:
            raise ValueError("Process-control source changed since native execution")
    junit = process["observations"]["process_tests"]["junit"]
    check_file(junit)
    if not process_test_verdict(Path(junit["path"]))["ok"]:
        raise ValueError("Required process controls are missing, skipped or failed")
    for decision in ("approve", "deny"):
        observed = observe_quickstart(Path(package["area"]) / f"project {decision} café", decision)
        expected, = [item for item in package["observations"]["quickstart"] if item["decision"] == decision]
        if observed != expected:
            raise ValueError("Retained quickstart effect or ledger changed")
    require_missing_provider_refusal(package["observations"]["setup"])
    run.payload["components"] = {"package": file_identity(package_path), "process": file_identity(process_path)}
    return package, process


def metal_log_observation(text: str) -> dict:
    """Pinned upstream b10809 log vocabulary; detection alone does not pass."""
    devices = re.findall(r"using device (Metal\w*) \(([^\r\n)]+)\)", text)
    offload = re.findall(r"offloaded (\d+)/(\d+) layers to GPU", text)
    buffers = re.findall(r"\b(Metal\w*) model buffer size\s*=\s*([\d.]+) MiB", text)
    allocated = any(name in {device[0] for device in devices} and float(size) > 0 for name, size in buffers)
    return {"metal_model_allocation_observed": bool(devices and allocated and any(int(n) > 0 for n, _ in offload)),
            "devices": devices, "gpu_layer_offload": offload, "metal_model_buffers_mib": buffers,
            "claim_limit": "Requires successful inference on this same owned server; not a performance benchmark"}
