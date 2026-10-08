"""Combine installed candidate, native process and actual-provider Mac acceptance."""
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import tempfile
from pathlib import Path

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orket.adapters.observability.logging_context import bind_logging, prepare_logging, select_logging_inputs
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from scripts.ci.macos_acceptance_evidence import CASE_IDS, admit_components, required_case_verdict
from scripts.ci.macos_provider_acceptance import exercise_provider, pass_case
from scripts.ci.record_quality_gate import source_identity
from scripts.ci.verify_candidate_install import PROBE, InstallEvidence, exercise_quickstart, exercise_setup
from scripts.ci.verify_installed_process_acceptance import candidate_inputs
from scripts.common.evidence_environment import utc_now_iso
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

REPORT = Path(".tmp/macos-support/native-acceptance.json")


async def admit_candidate(run: InstallEvidence, package_path: Path, process_path: Path) -> Path:
    run.payload["active_case"] = "MA-01"
    python, prefix, core, sdk = candidate_inputs(run, package_path)
    package, process = admit_components(run, package_path, process_path)
    probe = run.area / PROBE.name
    probe.write_bytes((run.repo / PROBE).read_bytes())
    observed = json.loads(await run.command(
        [str(python), "-I", str(probe), str(run.repo), str(prefix), str(core), str(sdk)], cwd=run.area))
    if observed != package["observations"]["installed"]:
        raise ValueError("Candidate interpreter, imports or installed bytes changed")
    run.payload["observations"]["installed"] = observed
    frozen = await run.command([str(python), "-I", "-m", "pip", "freeze", "--all"], cwd=run.area)
    earlier = process["commands"][-1]
    if earlier["argv"] != [str(python), "-I", "-m", "pip", "freeze", "--all"]:
        raise ValueError("Process component has no final dependency inventory")
    previous = await asyncio.to_thread(Path(earlier["stdout"]["path"]).read_bytes)
    if frozen.splitlines() != previous.splitlines():
        raise ValueError("Installed dependencies changed since native process proof")
    pass_case(run, "MA-01", {"installed": observed, "package": run.payload["components"]["package"],
                             "dependencies": run.payload["commands"][-1]["stdout"]})
    junit = process["observations"]["process_tests"]["junit"]
    for identity in ("MA-06", "MA-07"):
        pass_case(run, identity, {"junit": junit, "component": run.payload["components"]["process"],
                                 "scope": "Existing native command and independently observed descendant controls"})
    return python


async def exercise_failures(run: InstallEvidence, python: Path) -> None:
    # Repeat effects/refusals in the current dependency environment, after dev-extra installation.
    run.payload["active_case"] = "MA-03"
    await exercise_quickstart(run, python)
    pass_case(run, "MA-03", {"effects": run.payload["observations"]["quickstart"],
                             "ledger_verification_and_tamper_refusal": run.payload["commands"][-5:]})
    run.payload["active_case"] = "MA-09"
    await exercise_setup(run, python)
    pass_case(run, "MA-09", {"missing_provider": run.payload["observations"]["setup"]["missing_provider"],
                             "process_component": run.payload["components"]["process"],
                             "verification_refusal": "Native nonzero/overflow and uncertain acknowledgement tests",
                             "claim_limit": "Uncertainty cases use controlled model proposals and actual command/API/SQLite effects"})


def finish_verdict(run: InstallEvidence) -> None:
    verdict = required_case_verdict(run.payload["cases"], native_mac=run.payload["native_mac"])
    run.payload.update(verdict)
    if verdict["macos_acceptance_complete"]:
        run.payload.update(status="PASS", observed_result="success")
        return
    cases = run.payload["cases"]
    control = (run.payload["windows_control"] and cases["MA-05"]["status"] == "BLOCKED"
               and all(cases[key]["status"] == "PASS" and cases[key].get("evidence")
                       for key in CASE_IDS if key != "MA-05"))
    if not control:
        raise ValueError("All nine native Mac acceptance cases must pass")
    run.payload.update(status="CONTROL_PASS", observed_result="partial success")


async def verify(run: InstallEvidence, args: argparse.Namespace) -> int:
    try:
        allowed = platform.system() == "Windows" if args.windows_control else run.payload["native_mac"]
        if not allowed:
            run.payload.update(observed_path="blocked", observed_result="environment blocker")
            raise RuntimeError("Native Apple Silicon macOS required; select Windows control explicitly for non-Mac proof")
        python = await admit_candidate(run, (run.repo / args.candidate_receipt).resolve(),
                                        (run.repo / args.process_receipt).resolve())
        with bind_logging(await prepare_logging(select_logging_inputs(run.area, run.environment))):
            await exercise_failures(run, python)
            await exercise_provider(run, python, args.llama_server.expanduser().resolve(),
                                    args.model_file.expanduser().resolve(), DEFAULT_LOCAL_MODEL)
        if source_identity(run.repo) != run.payload["source"]:
            raise ValueError("Authored inputs changed during acceptance")
        run.payload["source_unchanged"] = True
        finish_verdict(run)
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        run.payload.update(status="FAIL", observed_result="failure", error="Acceptance interrupted")
        return 130
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, httpx.HTTPError) as exc:
        run.payload.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
        blocked = run.payload["observed_result"] == "environment blocker"
        if not blocked:
            run.payload["observed_result"] = "failure"
        identity = run.payload.get("active_case")
        if identity and run.payload["cases"][identity]["status"] != "PASS":
            run.payload["cases"][identity].update(status="BLOCKED" if blocked else "FAIL", reason=run.payload["error"])
        print(run.payload["error"], file=sys.stderr)
        return 1
    finally:
        if run.payload["status"] not in {"PASS", "CONTROL_PASS"}:
            run.payload["macos_acceptance_complete"] = False
        run.payload["finished_at_utc"] = utc_now_iso()
        write_payload_with_diff_ledger(run.area / "receipt.json", run.payload)
        run.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-receipt", type=Path, default=Path(".tmp/macos-support/package-install.json"))
    parser.add_argument("--process-receipt", type=Path, default=Path(".tmp/macos-support/process-acceptance.json"))
    parser.add_argument("--llama-server", type=Path, required=True)
    parser.add_argument("--model-file", type=Path, required=True, help="Prepared Qwen3.8 GGUF; the canonical model alias is used.")
    parser.add_argument("--windows-control", action="store_true", help="Exercise the harness on Windows; never Mac acceptance.")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    area = Path(tempfile.mkdtemp(prefix="orket-mac-acceptance-")).resolve()
    if area.is_relative_to(repo):
        parser.error("Temporary directory must be outside the checkout")
    run = InstallEvidence(repo, area, require_mac=not args.windows_control, report=REPORT)
    run.payload["environment"]["macos_version"] = platform.mac_ver()[0]
    run.payload.update(schema_version="orket.macos_acceptance.v1", scope="Required MA-01 through MA-09",
                       native_mac=(platform.system(), platform.machine()) == ("Darwin", "arm64"),
                       windows_control=args.windows_control,
                       cases={key: {"status": "BLOCKED", "reason": "Not executed", "evidence": {}} for key in CASE_IDS})
    run.save()
    print(f"Evidence: {run.path}\nRetained area: {area}", flush=True)
    return asyncio.run(verify(run, args))


if __name__ == "__main__":
    raise SystemExit(main())
