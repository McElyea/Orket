"""Run native lifetime and uncertainty controls against isolated candidate wheels."""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import tempfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.candidate_install_support import (
    file_identity,
    inspect_wheel,
    require_missing_provider_refusal,
    snapshot_packages,
)
from scripts.ci.installed_process_controls import MODULES, copy_process_harness, process_test_verdict
from scripts.ci.record_quality_gate import source_identity
from scripts.ci.verify_candidate_install import PROBE, InstallEvidence
from scripts.common.evidence_environment import utc_now_iso
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

REPORT = Path(".tmp/macos-support/process-acceptance.json")


def candidate_inputs(run: InstallEvidence, receipt: Path) -> tuple[Path, Path, Path, Path]:
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS" or payload.get("source_unchanged") is not True:
        raise ValueError("Passing isolated candidate-install receipt required")
    require_missing_provider_refusal(payload["observations"]["setup"])
    installed = payload["observations"]["installed"]
    if (installed["system"], installed["machine"]) != (platform.system(), platform.machine()):
        raise ValueError("Candidate was verified on a different host platform")
    prefix, python = Path(installed["prefix"]), Path(installed["executable"])
    # POSIX venv executables may symlink to the base interpreter. Preserve the
    # invoked venv path; the installed probe independently verifies sys.prefix.
    if prefix.resolve().is_relative_to(run.repo) or not python.absolute().is_relative_to(prefix.absolute()):
        raise ValueError("Candidate interpreter must stay in its external isolated prefix")
    wheels = {entry["namespace"]: entry for entry in payload["wheels"]}
    core, sdk = Path(wheels["orket"]["path"]), Path(wheels["orket_extension_sdk"]["path"])
    source = run.area / "current package inputs"
    snapshot = snapshot_packages(run.repo, source)
    if snapshot["sha256"] != payload["snapshot"]["sha256"]:
        raise ValueError("Authored package inputs changed; build and verify a fresh candidate first")
    run.payload["package_snapshot"] = {key: value for key, value in snapshot.items() if key != "inputs"}
    for namespace, path in (("orket", core), ("orket_extension_sdk", sdk)):
        if inspect_wheel(path, source, namespace)["sha256"] != wheels[namespace]["sha256"]:
            raise ValueError("Candidate wheel changed since installation")
    run.payload.update(candidate_receipt=file_identity(receipt), candidate_source=payload["source"], wheels=payload["wheels"])
    return python, prefix, core, sdk


async def exercise(run: InstallEvidence, receipt: Path) -> None:
    python, prefix, core, sdk = candidate_inputs(run, receipt)
    # Install the selected wheel's declared test tooling; do not invent a second dependency list.
    await run.command([str(python), "-I", "-m", "pip", "install", str(core) + "[dev]"], cwd=run.area, timeout_seconds=900)
    await run.command([str(python), "-I", "-m", "pip", "check"], cwd=run.area)
    probe = run.area / PROBE.name
    probe.write_bytes((run.repo / PROBE).read_bytes())
    output = await run.command([str(python), "-I", str(probe), str(run.repo), str(prefix), str(core), str(sdk)], cwd=run.area)
    run.payload["observations"]["installed"] = json.loads(output)
    harness = run.area / "native process harness café"
    run.payload["harness_files"] = copy_process_harness(run.repo, harness)
    junit = harness / "process-tests.xml"
    run.save()
    try:
        await run.command([str(python), "-I", "-m", "pytest", "-q", "--confcutdir=.", "--import-mode=importlib",
                           f"--junitxml={junit}", f"--basetemp={harness / 'runs'}", *MODULES],
                          cwd=harness, timeout_seconds=300)
    finally:
        if junit.exists():
            run.payload["observations"]["process_tests"] = {"junit": file_identity(junit), **process_test_verdict(junit)}
            run.save()
    if not run.payload["observations"].get("process_tests", {}).get("ok"):
        raise ValueError("Mandatory native process items were absent, skipped or failed")
    await run.command([str(python), "-I", "-m", "pip", "freeze", "--all"], cwd=run.area)


async def verify(run: InstallEvidence, receipt: Path, windows_control: bool) -> int:
    try:
        allowed = platform.system() == "Windows" if windows_control else (
            platform.system() == "Darwin" and platform.machine() == "arm64")
        if not allowed:
            run.payload.update(observed_path="blocked", observed_result="environment blocker")
            raise RuntimeError("Native Apple Silicon macOS required; Windows control mode must be explicitly selected")
        await exercise(run, receipt)
        if source_identity(run.repo) != run.payload["source"]:
            raise ValueError("Authored inputs changed during process acceptance")
        run.payload.update(status="PASS", source_unchanged=True, observed_result="success")
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        run.payload.update(status="FAIL", observed_result="failure", error="Process acceptance interrupted")
        return 130
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        run.payload.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        if run.payload["observed_result"] != "environment blocker":
            run.payload["observed_result"] = "failure"
        print(run.payload["error"], file=sys.stderr)
        return 1
    finally:
        run.payload["finished_at_utc"] = utc_now_iso()
        write_payload_with_diff_ledger(run.area / "receipt.json", run.payload)
        run.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-receipt", type=Path, default=Path(".tmp/macos-support/package-install.json"))
    parser.add_argument("--windows-control", action="store_true", help="Explicit Windows harness proof; never Mac acceptance.")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    area = Path(tempfile.mkdtemp(prefix="orket-native-process-")).resolve()
    if area.is_relative_to(repo):
        parser.error("Temporary directory must be outside the checkout")
    run = InstallEvidence(repo, area, require_mac=not args.windows_control, report=REPORT)
    run.payload.update(scope="Installed native lifetime and uncertainty controls; not full MA-01..09 acceptance",
                       windows_control=args.windows_control,
                       coverage={"MA-06": "native verification and capture cases", "MA-07": "descendant cleanup cases",
                                 "MA-09": "process uncertainty/failure component only"})
    run.save()
    print(f"Evidence: {run.path}\nRetained area: {area}", flush=True)
    return asyncio.run(verify(run, (repo / args.candidate_receipt).resolve(), args.windows_control))


if __name__ == "__main__":
    raise SystemExit(main())
