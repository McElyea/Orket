"""Trusted SDK fixtures with independent native process and filesystem observations."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import psutil

from orket.extensions.models import ExtensionRecord, _ExtensionManifestEntry
from orket.extensions.sdk_capability_authorization import (
    HostCapabilityControls,
    SdkCapabilityAuditCase,
    build_host_authorization_envelope,
)
from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.workload import WorkloadContext

WORKER = Path(__file__).parents[1] / "integration" / "verification_lifetime_worker.py"
SOURCE = '''import json
import os
import subprocess
import sys
import time
from pathlib import Path
from orket_extension_sdk.result import WorkloadResult

def run(ctx, payload):
    root = Path(ctx.workspace_root)
    (root / "sdk-pid").write_text(str(os.getpid()))
    (root / "sdk-run-id").write_text(ctx.run_id)
    (root / "sdk-effect").write_text("executed")
    mode = payload.get("mode", "success")
    if mode == "missing":
        os._exit(23)
    if mode == "output-limit":
        sys.stdout.write("x" * (5 * 1024 * 1024))
        sys.stdout.flush()
    if payload.get("tree"):
        subprocess.Popen([sys.executable, payload["worker"], str(root), "2", *payload["flags"]])
        deadline = time.monotonic() + 20
        while not (root / "release-sdk").exists() and time.monotonic() < deadline:
            time.sleep(.01)
    if mode == "error":
        raise ValueError("controlled workload failure")
    return WorkloadResult(ok=True, output={"effect": "executed"})
'''


def sdk_request(root, *, mode="success", tree=False, flags=()):
    source_root = root / "extension"
    source_root.mkdir()
    name = "sdk_lifetime_" + hashlib.sha256(str(root).encode()).hexdigest()[:16]
    (source_root / f"{name}.py").write_text(SOURCE, encoding="utf-8")
    entry = _ExtensionManifestEntry("fixture", "1", entrypoint=f"{name}:run", contract_style="sdk_v0")
    extension = ExtensionRecord("lifetime.fixture", "1", "fixture", "v0", str(source_root), "", "", (entry,),
        contract_style="sdk_v0", allowed_stdlib_modules=("json", "os", "pathlib", "subprocess", "sys", "time"))
    context = WorkloadContext("lifetime.fixture", "fixture", "observed", root, root, root, CapabilityRegistry())
    envelope = build_host_authorization_envelope(extension_id=extension.extension_id, workload_id=entry.workload_id,
        run_id=context.run_id, declared_capabilities=[], controls=HostCapabilityControls())
    return dict(extension=extension, workload=entry, sdk_ctx=context,
        input_payload=dict(mode=mode, tree=tree, flags=list(flags), worker=str(WORKER)),
        authorization_envelope=envelope, audit_case=SdkCapabilityAuditCase())


def owned_fixture_processes(root):
    """Track only marker-identified fixtures and their ancestors below this pytest."""
    markers = list(root.glob("ready-*.json"))
    pids = [json.loads(p.read_text(encoding="utf-8"))["pid"] for p in markers]
    if (root / "sdk-pid").exists():
        pids.append(int((root / "sdk-pid").read_text()))
    observed = {}
    for pid in pids:
        try:
            process = psutil.Process(pid)
            parents = process.parents()
            if os.getpid() not in {parent.pid for parent in parents}:
                continue
            observed[process.pid] = process
            for parent in parents:
                if parent.pid == os.getpid():
                    break
                observed[parent.pid] = parent
        except psutil.NoSuchProcess:
            continue
    return list(observed.values())
