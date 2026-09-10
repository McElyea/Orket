"""Exercise core 0.6.0 release entrypoints against installed wheels."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402

OUTPUT = ROOT / "benchmarks/results/releases/0.6.0/surfaces.json"


def _command(command: list[str], directory: Path, env: dict, *, claim: str, expected: int = 0) -> dict:
    result = subprocess.run(command, cwd=directory, env=env, input="quit\n", text=True,
                            capture_output=True, timeout=90, check=False)
    output = result.stdout + result.stderr
    path = "degraded" if "continuing in degraded mode" in output else "primary"
    return {"command": command, "proof_mode": "live", "observed_path": path,
            "observed_result": "success" if result.returncode == expected and claim in output else "failure",
            "exit_code": result.returncode, "expected_exit_code": expected, "required_claim": claim,
            "output": output}


def _api(python: Path, directory: Path, env: dict) -> dict:
    shutil.copy2(ROOT / "server.py", directory / "server.py")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [str(python), "server.py", "--host", "127.0.0.1", "--port", str(port), "--no-reload"]
    log = directory / "api.log"
    response = None
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=directory, env=env, stdout=stream, stderr=stream)
        try:
            deadline = time.monotonic() + 45
            with httpx.Client(timeout=2) as client:
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        response = client.get(f"http://127.0.0.1:{port}/health")
                        if response.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass  # Bounded startup polling; failure is recorded below with process logs.
                    time.sleep(0.2)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
    return {"command": command, "proof_mode": "live", "observed_path": "primary",
            "observed_result": "success" if response is not None and response.status_code == 200 else "failure",
            "http_status": None if response is None else response.status_code,
            "body": None if response is None else response.json(), "process_reaped": process.poll() is not None,
            "output": log.read_text(encoding="utf-8"),
            "teardown": "Health-only server terminated and reaped; graceful task teardown is covered by agent acceptance."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path)
    args = parser.parse_args()
    python = args.python.resolve()
    cli = python.parent / ("orket.exe" if os.name == "nt" else "orket")
    parent = ROOT / ".tmp/governed-agent-release-surfaces"
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="execution-", dir=parent))
    env = {**os.environ, "ORKET_DISABLE_SANDBOX": "1", "ORKET_API_KEY": "release-local-health-probe"}
    records = {
        "default_runtime_entrypoint": _command([str(cli), "runtime", "--workspace", str(directory / "workspace")],
                                               directory, env, claim="ORKET DRIVER (Interactive)"),
        "handled_runtime_failure": _command([str(cli), "runtime", "extensions", "unsupported"],
                                            directory, env, claim="orket runtime extensions list", expected=1),
        "governed_run_workflow": _command([str(cli), "demo", "governed-run", "--workspace", str(directory)],
                                         directory, env, claim="[orket] Run completed"),
        "api_runtime_entrypoint": _api(python, directory, env),
    }
    evidence = directory / ".runs/governed-run-demo/evidence.json"
    records["governed_run_workflow"]["durable_evidence_present"] = evidence.is_file()
    if evidence.is_file():
        records["governed_run_workflow"]["durable_evidence_sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
    else:
        records["governed_run_workflow"]["observed_result"] = "failure"
    observed_path = "degraded" if any(r["observed_path"] == "degraded" for r in records.values()) else "primary"
    payload = {"proof_mode": "live", "observed_path": observed_path, "records": records,
               "observed_result": "success" if all(r["observed_result"] == "success" for r in records.values()) else "failure",
               "evidence_directory": str(directory),
               "scope": "Installed core entrypoints; source server launcher copied alone into an isolated workspace."}
    write_payload_with_diff_ledger(OUTPUT, payload)
    print(json.dumps({"output": str(OUTPUT), "result": payload["observed_result"]}, indent=2))
    return 0 if payload["observed_result"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
