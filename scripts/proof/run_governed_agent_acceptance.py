"""Run live acceptance against installed artifacts and retain a diff-ledger report."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from orket.runtime.config.defaults import DEFAULT_LOCAL_MODEL, DEFAULT_LOCAL_PROVIDER  # noqa: E402
from orket.runtime.config.provider_runtime_target import default_base_url  # noqa: E402
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402

OUTPUT = ROOT / "benchmarks/results/governed_agent/acceptance.json"
MODULES = (
    "tests/e2e/test_governed_agent_ollama.py",
    "tests/e2e/test_governed_agent_supervisor_ollama.py",
    "tests/e2e/test_governed_agent_effect_ollama.py",
    "tests/e2e/test_governed_agent_process_recovery.py",
    "tests/e2e/governed_agent_process_worker.py",
    "tests/runtime/governed_agent_test_support.py",
    "tests/e2e/test_governed_agent_llama_cpp.py",
)


def _harness(directory: Path) -> None:
    for relative in MODULES:
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    (directory / "conftest.py").write_text(
        "from pathlib import Path\nimport sysconfig\nimport orket\nimport orket_extension_sdk\n"
        "import orket_governed_local_agent\n\n"
        "def pytest_sessionstart(session):\n"
        "    installed = Path(sysconfig.get_path('purelib')).resolve()\n"
        "    for module in (orket, orket_extension_sdk, orket_governed_local_agent):\n"
        "        path = Path(module.__file__).resolve()\n"
        "        assert path.is_relative_to(installed), path\n"
        "        print(f'INSTALLED_IMPORT {module.__name__}: {path}')\n",
        encoding="utf-8",
    )
    (directory / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    end_to_end: live installed artifact acceptance\n"
        "asyncio_default_fixture_loop_scope = function\n", encoding="utf-8",
    )


def _database_evidence(path: Path) -> dict:
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        iterations = [dict(zip(("request", "result", "decision", "decision_inputs", "binding"),
                              [json.loads(value) if value else None for value in row], strict=True))
                      for row in conn.execute("SELECT request_json,result_json,decision_json,decision_inputs_json,binding_json "
                                              "FROM governed_agent_invocations ORDER BY rowid")]
        receipts = [json.loads(row[0])["receipt"] for row in conn.execute(
            "SELECT result_json FROM governed_agent_calls WHERE result_json IS NOT NULL AND operation='model.call.v1'"
        )]
        runs = [json.loads(row[0]) for row in conn.execute("SELECT payload_json FROM control_plane_runs")]
        truth = [json.loads(row[0]) for row in conn.execute("SELECT payload_json FROM final_truth_records")]
    return {
        "database": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "runs": runs, "final_truth": truth,
        "iterations": [{"identity": item["request"]["identity"],
                        "binding": item["binding"], "model_profiles": item["request"]["model_profiles"],
                        "extension_config": item["request"]["extension_config"],
                        "context_refs": item["request"]["authoritative_context_refs"],
                        "prior_refs": item["request"]["prior_verified_output_refs"],
                        "proposal": None if not item["result"] else item["result"]["advisory_proposal"],
                        "decision": item["decision"], "decision_inputs": item["decision_inputs"]}
                       for item in iterations],
        "model_calls": len(receipts), "repair_calls": sum("repair" in item["call_id"] for item in receipts),
        "input_tokens": sum(item["input_tokens"] for item in receipts) if all(
            item["input_tokens"] is not None for item in receipts) else None,
        "output_tokens": sum(item["output_tokens"] for item in receipts) if all(
            item["output_tokens"] is not None for item in receipts) else None,
        "peak_admitted_concurrency": 1 if receipts else 0,
        "concurrency_basis": "sequential agent_stdio_ipc.v1 broker; capacity limit 1 in live API harness",
        "receipts": receipts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, type=Path, help="Clean artifact environment interpreter.")
    parser.add_argument("--extension-root", required=True, type=Path, help="Extracted external reference sdist.")
    parser.add_argument("--artifact", action="append", type=Path, required=True, help="Each exact built wheel/sdist.")
    parser.add_argument("--provider", choices=("llama_cpp", "ollama"), default=DEFAULT_LOCAL_PROVIDER)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL, help="Exact served model for llama.cpp acceptance.")
    parser.add_argument("--base-url", default="", help="Selected provider endpoint override.")
    args = parser.parse_args()
    parent = ROOT / ".tmp/governed-agent-acceptance"
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="execution-", dir=parent))
    _harness(directory)
    env = _acceptance_environment(args)
    modules = ([MODULES[-1], MODULES[3]] if args.provider == "llama_cpp" else list(MODULES[:4]))
    junit = directory / "junit.xml"
    command = [str(args.python.resolve()), "-I", "-m", "pytest", "-q", "-s", "--confcutdir=.",
               "--import-mode=importlib", "--tb=short", f"--junitxml={junit}",
               f"--basetemp={directory / 'runs'}", *modules]
    start = time.monotonic()
    result = subprocess.run(command, cwd=directory, env=env, text=True, capture_output=True, check=False)
    elapsed = time.monotonic() - start
    (directory / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    inventory = _inventory(args.provider, args.base_url or default_base_url(args.provider))
    tests = _tests(junit)
    accepted = result.returncode == 0 and bool(tests) and all(item["result"] == "success" for item in tests)
    accepted = accepted and inventory.get("observed_result") == "success"
    payload = {
        "schema_version": "governed_agent_acceptance.v1", "observed_path": "primary",
        "observed_result": "success" if accepted else "failure", "proof_mode": "live",
        "command": command, "elapsed_seconds_including_model_loading": elapsed,
        "pytest_exit_code": result.returncode, "log": str(directory / "pytest.log"),
        "tests": tests, "inventory": inventory,
        "build": _build_evidence(args),
        "cases": [_database_evidence(path) for path in sorted((directory / "runs").glob("*/agent.sqlite3"))
                  if not path.parent.name.endswith("current")],
        "limitations": ["Inventory digests are observed separately; provider receipts do not attest loaded weight digests.",
                        "Abrupt process exit is injected immediately before/after the real write; other crash windows remain fail-closed.",
                        "Trusted extension process is not hostile-code containment.",
                        "Sequential capability proof does not establish comparative quality or production soak."],
    }
    write_payload_with_diff_ledger(OUTPUT, payload)
    print(json.dumps({"output": str(OUTPUT), "result": payload["observed_result"],
                      "tests": len(payload["tests"]), "elapsed_seconds": elapsed}, indent=2))
    return 0 if accepted else result.returncode or 1


def _build_evidence(args) -> dict:
    probe = subprocess.run([str(args.python.resolve()), "-I", "-c",
        "import importlib.metadata as m,json; print(json.dumps({n:m.version(n) for n in "
        "('orket','orket-extension-sdk','orket-governed-local-agent')}))"],
        capture_output=True, text=True, check=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout
    return {"installed_versions": json.loads(probe.stdout), "base_commit": commit,
            "worktree_dirty": bool(status), "source_basis": "uncommitted working-tree candidate",
            "artifacts": [{"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path in args.artifact]}


def _acceptance_environment(args) -> dict[str, str]:
    env = {**os.environ, "ORKET_DISABLE_SANDBOX": "1",
           "ORKET_RUN_LIVE_AGENT_OLLAMA": "1" if args.provider == "ollama" else "0",
           "ORKET_RUN_LIVE_AGENT_LLAMA_CPP": "1" if args.provider == "llama_cpp" else "0",
           "ORKET_GOVERNED_AGENT_PROVIDER": args.provider,
           "ORKET_GOVERNED_AGENT_EXTENSION_ROOT": str(args.extension_root.resolve())}
    base_url = args.base_url or default_base_url(args.provider)
    env["ORKET_GOVERNED_AGENT_BASE_URL"] = base_url
    if args.provider == "llama_cpp":
        env["ORKET_GOVERNED_AGENT_MODEL"] = args.model
        env["ORKET_LLM_LLAMA_CPP_BASE_URL"] = base_url
    return env


def _tests(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [{"name": item.attrib["name"], "seconds": float(item.attrib["time"]),
             "result": "failure" if item.find("failure") is not None or item.find("error") is not None
             else "skipped" if item.find("skipped") is not None else "success"}
            for item in ET.parse(path).iter("testcase")]


def _inventory(provider: str, base_url: str) -> dict:
    try:
        if provider == "llama_cpp":
            response = httpx.get(base_url.rstrip("/") + "/models", timeout=15)
            response.raise_for_status()
            props = httpx.get(base_url.removesuffix("/v1").rstrip("/") + "/props", timeout=15)
            props.raise_for_status()
            return {"provider": provider, "observed_result": "success",
                    "provider_version": props.json().get("build_info"), "models": response.json()["data"]}
        with httpx.Client(base_url=base_url, timeout=15) as client:
            tags = client.get("/api/tags")
            version = client.get("/api/version")
            tags.raise_for_status()
            version.raise_for_status()
        return {"provider": provider, "observed_result": "success", "provider_version": version.json()["version"],
                "models": [{"name": item["name"], "digest": item["digest"]}
                           for item in tags.json()["models"]]}
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        return {"observed_result": "environment blocker", "error_class": type(exc).__name__}


if __name__ == "__main__":
    raise SystemExit(main())
