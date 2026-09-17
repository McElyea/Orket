"""Explicit live Docker fixture acceptance; removes only containers created by this invocation."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from orket.adapters.execution.fixture_docker import OWNER_LABEL
from orket.application.services.fixture_container_owner import FixtureContainerCancelled
from orket.application.services.fixture_verification_service import FixtureVerificationService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.schema import IssueVerification, VerificationScenario
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

FIXTURE = '''import subprocess, sys, time
from pathlib import Path
def verify(data):
    if data['case'] in {'success', 'mismatch'}:
        return 1
    grandchild = "import time; from pathlib import Path; Path('/tmp/grandchild-ready').touch(); time.sleep(20)"
    child = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-I', '-c', " + repr(grandchild) + "]); time.sleep(20)"
    subprocess.Popen([sys.executable, '-I', '-c', child])
    while not Path('/tmp/grandchild-ready').exists():
        time.sleep(0.02)
    if data['case'] == 'leader-exit':
        return 1
    time.sleep(20)
    return 1
'''


class Inputs(RuntimeInputService):
    def __init__(self, identity):
        self.identity = identity

    def create_effect_owner_id(self):
        return self.identity


def docker(*argv, check=True):
    # This standalone proof driver observes the daemon independently of the implementation.
    return subprocess.run(["docker", *argv], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=15, check=check)


def exact_container(name):
    result = docker("container", "ls", "--all", "--no-trunc", "--filter", f"name={name}",
                    "--format", "{{json .}}")
    return [row["ID"] for row in map(json.loads, result.stdout.splitlines()) if row["Names"] == name]


def cleanup_proof_container(name, owner_id):
    removed = []
    for identity in exact_container(name):
        observed = json.loads(docker("container", "inspect", identity).stdout)[0]
        assert observed["Name"] == "/" + name and observed["Config"]["Labels"][OWNER_LABEL] == owner_id
        docker("container", "rm", "--force", "--volumes", identity)
        removed.append(identity)
    assert exact_container(name) == []
    return removed


async def await_descendants(name, task):
    for _ in range(200):
        if task.done():
            await task
            raise AssertionError("Fixture ended before descendant observation")
        found = await asyncio.to_thread(exact_container, name)
        if found:
            result = await asyncio.to_thread(docker, "container", "top", found[0], "-eo", "pid,ppid,args", check=False)
            if result.returncode == 0 and len(result.stdout.splitlines()) >= 4:
                return {"container_id": found[0], "top": result.stdout}
        await asyncio.sleep(0.025)
    raise AssertionError("Fixture descendants were not observed")


async def run_case(root, case):
    identity = str(uuid4())
    name = "orket-verification-" + identity.replace("-", "")
    root.mkdir(parents=True)
    (root / "verification").mkdir()
    (root / "verification/fixture.py").write_text(FIXTURE, encoding="utf-8")
    verification = IssueVerification(fixture_path="verification/fixture.py", scenarios=[
        VerificationScenario(id="one", description=case, input_data={"case": case},
                             expected_output=2 if case == "mismatch" else 1)])
    environment = {**os.environ, "ORKET_VERIFY_EXECUTION_MODE": "container",
                   "ORKET_VERIFY_TIMEOUT_SEC": "4" if case == "timeout" else "15"}
    service = FixtureVerificationService(root, environment=environment, runtime_inputs=Inputs(identity))
    task = asyncio.create_task(service.verify(verification))
    row = {"case": case, "name": name, "owner_id": identity, "path": "primary", "result": "failure"}
    try:
        if case in {"cancel", "repeated-cancel", "timeout"}:
            row["descendants_before_stop"] = await await_descendants(name, task)
        if case in {"cancel", "repeated-cancel"}:
            task.cancel()
            if case == "repeated-cancel":
                for _ in range(30):
                    if task.done():
                        break
                    await asyncio.sleep(0.01)
                    task.cancel()
            try:
                await task
            except FixtureContainerCancelled as exc:
                row["lifetime"] = exc.lifetime.lifetime()
            else:
                raise AssertionError("Expected fixture cancellation")
            assert verification.scenarios[0].status == "pending" and verification.last_run is None
        else:
            result = await task
            row["verification"] = result.model_dump()
            row["lifetime"] = result.process_lifetime
            assert result.passed == (0 if case in {"mismatch", "timeout"} else 1)
        assert row["lifetime"]["cleanup_confirmed"] is True
        assert await asyncio.to_thread(exact_container, name) == []
        row["absence_observed_independently"] = True
        row["result"] = "success"
    except (AssertionError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        row["proof_driver_removed"] = await asyncio.to_thread(cleanup_proof_container, name, identity)
    return row


async def run(output):
    case_root = output.parent / ("fixture-container-" + uuid4().hex)
    rows = []
    for case in ("success", "mismatch", "leader-exit", "timeout", "cancel", "repeated-cancel"):
        row = await run_case(case_root / case, case)
        rows.append(row)
        print(f"{case}: {row['result']} (proof cleanup: {row['proof_driver_removed']})", flush=True)
        write_payload_with_diff_ledger(output, {"proof": "live Docker fixture acceptance", "path": "primary",
            "result": "partial success", "python": sys.version, "rows": rows})
    payload = {"proof": "live Docker fixture acceptance", "path": "primary", "python": sys.version,
               "docker_context": docker("context", "show").stdout.strip(), "rows": rows,
               "result": "success" if all(row["result"] == "success" for row in rows) else "failure"}
    write_payload_with_diff_ledger(output, payload)
    return 0 if payload["result"] == "success" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/acceptance/fixture_container_lifetime.json"))
    args = parser.parse_args()
    os.environ["ORKET_DISABLE_SANDBOX"] = "1"
    raise SystemExit(asyncio.run(run(args.output.resolve())))
