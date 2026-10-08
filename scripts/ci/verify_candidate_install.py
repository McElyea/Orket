"""Build clean wheels and prove installed public commands outside the source checkout."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from scripts.ci.candidate_install_support import (
    MISSING_PROVIDER_MODEL,
    file_identity,
    inspect_wheel,
    observe_quickstart,
    require_missing_provider_refusal,
    snapshot_packages,
)
from scripts.ci.record_quality_gate import source_identity
from scripts.common.evidence_environment import utc_now_iso
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

REPORT = Path(".tmp/macos-support/package-install.json")
PROBE = Path("scripts/ci/installed_candidate_probe.py")


class InstallEvidence:
    def __init__(self, repo: Path, area: Path, *, require_mac: bool, report: Path = REPORT):
        self.repo, self.area, self.path = repo, area, repo / report
        self.owner = CommandProcessSupervisor(area, cancellation_event="candidate_install_interrupted")
        self.environment = {key: value for key, value in os.environ.items()
                            if not key.upper().startswith(("PYTHON", "ORKET_", "PIP_"))
                            and key.upper() != "VIRTUAL_ENV"}
        self.environment.update(ORKET_DISABLE_SANDBOX="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                                PYTHONNOUSERSITE="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INPUT="1",
                                PIP_CONFIG_FILE=os.devnull)
        self.payload: dict[str, Any] = {
            "schema_version": "orket.candidate_install.v1", "status": "RUNNING",
            "scope": "installed candidates and deterministic quickstart; no provider or full Mac acceptance",
            "macos_acceptance_complete": False, "require_macos_arm64": require_mac,
            "source": source_identity(repo), "area": str(area), "process_pid": os.getpid(),
            "retained_receipt": str(area / "receipt.json"),
            "environment": {"system": platform.system(), "machine": platform.machine(),
                            "release": platform.release(), "python": platform.python_version(),
                            "executable": sys.executable},
            "started_at_utc": utc_now_iso(), "commands": [], "observations": {},
            "observed_path": "primary", "observed_result": "partial success",
        }
        self.save()

    def save(self) -> None:
        write_payload_with_diff_ledger(self.path, self.payload)

    async def command(self, argv: list[str], *, cwd: Path, expected: int = 0,
                      timeout_seconds: float = 120, input_data: bytes | None = None) -> bytes:
        number = len(self.payload["commands"]) + 1
        record: dict[str, Any] = {"argv": argv, "cwd": str(cwd), "expected_exit": expected,
                                  "timeout_seconds": timeout_seconds, "started_at_utc": utc_now_iso(), "status": "RUNNING"}
        self.payload["commands"].append(record)
        self.save()
        print(f"[{number}] {Path(argv[0]).name}: {' '.join(argv[1:4])}", flush=True)
        cancelled = False
        try:
            result = await self.owner.run(argv, cwd=cwd, environment=self.environment, timeout_seconds=timeout_seconds,
                                          output_limit_bytes=16 * 1024 * 1024, input_data=input_data)
        except CommandProcessCancelled as exc:
            result, cancelled = exc.lifetime, True
        record.update(returncode=result.returncode, lifetime=result.lifetime(), finished_at_utc=utc_now_iso())
        for name, content in (("stdout", result.stdout), ("stderr", result.stderr)):
            path = self.area / f"command-{number}.{name}.log"
            path.write_bytes(content)
            record[name] = file_identity(path)
        good = (not cancelled and result.returncode == expected and result.reason == "completed"
                and result.cleanup_confirmed and result.capture_complete)
        record["status"] = "PASS" if good else "FAIL"
        if platform.system() == "Darwin" and result.backend == "unavailable" and result.command_pid is None:
            self.payload.update(observed_path="blocked", observed_result="environment blocker")
        self.save()
        if not good:
            raise RuntimeError(f"Command {number} did not meet exit/capture/cleanup requirements; see {self.path}")
        return result.stdout


async def build_and_install(run: InstallEvidence) -> tuple[Path, Path, Path]:
    source, dist, prefix = run.area / "source", run.area / "wheels", run.area / "candidate"
    snapshot = snapshot_packages(run.repo, source)
    write_payload_with_diff_ledger(run.repo / ".tmp/macos-support/package-inputs.json", snapshot)
    run.payload["snapshot"] = {key: value for key, value in snapshot.items() if key != "inputs"}
    run.save()
    dist.mkdir()
    for package_root in (source / "orket_extension_sdk", source):
        await run.command([sys.executable, "-I", "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(dist),
                           str(package_root)], cwd=run.area, timeout_seconds=900)
    wheels = {name: list(dist.glob(pattern)) for name, pattern in
              (("core", "orket-*.whl"), ("sdk", "orket_extension_sdk-*.whl"))}
    if any(len(paths) != 1 for paths in wheels.values()):
        raise ValueError("Expected exactly one core wheel and one SDK wheel from fresh sources")
    core, sdk = wheels["core"][0], wheels["sdk"][0]
    run.payload["wheels"] = [inspect_wheel(core, source, "orket"), inspect_wheel(sdk, source, "orket_extension_sdk")]
    run.save()
    await run.command([sys.executable, "-I", "-m", "venv", str(prefix)], cwd=run.area)
    python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    await run.command([str(python), "-I", "-m", "pip", "install", str(sdk), str(core)],
                       cwd=run.area, timeout_seconds=900)
    await run.command([str(python), "-I", "-m", "pip", "check"], cwd=run.area)
    await run.command([str(python), "-I", "-m", "pip", "freeze", "--all"], cwd=run.area)
    probe = run.area / PROBE.name
    probe.write_bytes((run.repo / PROBE).read_bytes())
    output = await run.command([str(python), "-I", str(probe), str(run.repo), str(prefix), str(core), str(sdk)],
                               cwd=run.area)
    run.payload["observations"]["installed"] = json.loads(output)
    run.save()
    return python, core, sdk


async def exercise_quickstart(run: InstallEvidence, python: Path) -> None:
    executable = python.parent / ("orket-quickstart.exe" if os.name == "nt" else "orket-quickstart")
    observations = []
    for decision in ("approve", "deny"):
        project = run.area / f"project {decision} café"
        project.mkdir()
        await run.command([str(executable), "--workspace", str(project), "--decision", decision], cwd=project)
        observed = observe_quickstart(project, decision)
        ledger = Path(observed["ledger"]["path"])
        # A fresh interpreter reopens retained state in a path with spaces and Unicode.
        await run.command([str(python), "-I", "-m", "orket.quickstart.verify_ledger", str(ledger)], cwd=project)
        if file_identity(ledger) != observed["ledger"]:
            raise ValueError("Ledger changed during read-only verification")
        tampered = project / "tampered-ledger.jsonl"
        rows = (await asyncio.to_thread(ledger.read_text, encoding="utf-8")).splitlines()
        first = json.loads(rows[0])
        first["payload"]["demo"] = "changed after execution"
        rows[0] = json.dumps(first)
        tampered.write_text("\n".join(rows) + "\n", encoding="utf-8")
        await run.command([str(python), "-I", "-m", "orket.quickstart.verify_ledger", str(tampered)],
                           cwd=project, expected=1)
        observations.append(observed)
    run.payload["observations"]["quickstart"] = observations
    run.save()


async def exercise_setup(run: InstallEvidence, python: Path) -> None:
    executable = python.parent / ("orket.exe" if os.name == "nt" else "orket")
    project = run.area / "configured project café"
    # Hold an unlistened port to make the missing-provider control independent of host services.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        endpoint = f"http://127.0.0.1:{unavailable.getsockname()[1]}/v1"
        await run.command([str(executable), "setup", "--project", str(project), "--non-interactive",
                           "--provider", "llama_cpp", "--base-url", endpoint, "--model-id", MISSING_PROVIDER_MODEL,
                           "--gguf-root", str(run.area / "models"), "--skip-check", "--run-example",
                           "--decision", "approve"], cwd=run.area)
        observed = observe_quickstart(project / "workspace", "approve")
        await run.command([str(python), "-I", "-m", "orket.quickstart.verify_ledger", observed["ledger"]["path"]],
                           cwd=run.area)
        # Use doctor's valid default budget; a shorter-than-connect timeout fails
        # provider construction before the unavailable endpoint is ever attempted.
        stdout = await run.command([str(executable), "doctor", "--project", str(project), "--json"],
                                    cwd=run.area, expected=1)
    diagnostic = json.loads(stdout)
    run.payload["observations"]["setup"] = {"project": str(project), "quickstart": observed,
                                              "missing_provider_endpoint": endpoint, "missing_provider": diagnostic}
    run.save()
    require_missing_provider_refusal(run.payload["observations"]["setup"])


async def verify(run: InstallEvidence) -> int:
    try:
        if run.payload["require_macos_arm64"] and (platform.system(), platform.machine()) != ("Darwin", "arm64"):
            run.payload.update(observed_path="blocked", observed_result="environment blocker")
            raise RuntimeError("Native Apple Silicon macOS interpreter required; this host cannot prove Mac acceptance")
        python, _, _ = await build_and_install(run)
        for name, arguments in (("orket", ["--help"]), ("orket", ["runtime", "--help"]),
                                ("orket", ["setup", "--help"]), ("orket", ["doctor", "--help"]),
                                ("orket-prompts", ["--help"]), ("orket-quickstart", ["--help"])):
            executable = python.parent / (name + ".exe" if os.name == "nt" else name)
            await run.command([str(executable), *arguments], cwd=run.area)
        await exercise_quickstart(run, python)
        await exercise_setup(run, python)
        if source_identity(run.repo) != run.payload["source"]:
            raise ValueError("Authored inputs changed during candidate verification; evidence is stale")
        run.payload.update(status="PASS", source_unchanged=True, observed_result="success")
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        run.payload.update(status="FAIL", observed_result="failure", error="Candidate verification interrupted")
        return 130
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        if run.payload["observed_result"] != "environment blocker":
            run.payload["observed_result"] = "failure"
        run.payload.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        print(run.payload["error"], file=sys.stderr)
        return 1
    finally:
        run.payload["finished_at_utc"] = utc_now_iso()
        # Immutable candidate evidence survives replacement of the one canonical latest result.
        write_payload_with_diff_ledger(run.area / "receipt.json", run.payload)
        run.save()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--require-macos-arm64", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve(strict=True)
    # Retain candidates, environments and logs for inspection. Never overwrite a prior run.
    area = Path(tempfile.mkdtemp(prefix="orket-candidate-")).resolve()
    if area.is_relative_to(repo):
        parser.error("System temporary directory must be outside the source checkout")
    run = InstallEvidence(repo, area, require_mac=args.require_macos_arm64)
    print(f"Evidence: {run.path}\nRetained candidate area: {area}", flush=True)
    return asyncio.run(verify(run))


if __name__ == "__main__":
    raise SystemExit(main())
