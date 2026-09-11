"""Run source-worktree llama.cpp integration proof with durable receipts and rerun history."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402
from scripts.proof.run_governed_agent_acceptance import _database_evidence, _tests  # noqa: E402

OUTPUT = ROOT / "benchmarks/results/providers/llama_cpp_integration.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Exact served GGUF filename-stem alias.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--extension-root", type=Path, required=True)
    args = parser.parse_args()
    root = ROOT / ".tmp/llama-cpp-integration"
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="proof-", dir=root))
    env = dict(os.environ)
    env.update({"ORKET_DISABLE_SANDBOX": "1", "ORKET_RUN_LIVE_AGENT_LLAMA_CPP": "1",
                "ORKET_GOVERNED_AGENT_MODEL": args.model, "ORKET_GOVERNED_AGENT_PROVIDER": "llama_cpp",
                "ORKET_GOVERNED_AGENT_BASE_URL": args.base_url, "ORKET_LLAMA_CPP_BASE_URL": args.base_url,
                "ORKET_LLM_LLAMA_CPP_BASE_URL": args.base_url,
                "ORKET_GOVERNED_AGENT_EXTENSION_ROOT": str(args.extension_root.resolve())})
    junit = directory / "junit.xml"
    command = [sys.executable, "-m", "pytest", "-q", "--tb=short", f"--junitxml={junit}",
               f"--basetemp={directory / 'runs'}", "tests/e2e/test_governed_agent_llama_cpp.py",
               "tests/live/test_llama_cpp_feature_paths.py"]
    start = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    elapsed = time.monotonic() - start
    log = directory / "pytest.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    tests = _tests(junit)
    passed = result.returncode == 0 and bool(tests) and all(row["result"] == "success" for row in tests)
    cases = [_case_evidence(path) for path in sorted((directory / "runs").glob("*/agent.sqlite3"))
             if not path.parent.name.endswith("current")]
    server = _server_metadata(args.base_url)
    passed = passed and server.get("status") != "unavailable" and bool(server.get("chat_template"))
    payload = {"schema_version": "llama_cpp_feature_integration.v1", "proof_mode": "live",
               "source_basis": "source worktree; not installed-release acceptance", "observed_path": "primary",
               "observed_result": "success" if passed else "failure", "model": args.model,
               "command": command, "elapsed_seconds": elapsed, "pytest_exit_code": result.returncode,
               "log": str(log), "tests": tests, "cases": cases, "server": server,
               "limitations": ["Single exact served model; no multi-model capacity or quality claim.",
                               "Template metadata is captured, not formal promotion-volume or LP-16 audit proof.",
                               "Operator owns llama-server lifecycle; no unload is attempted.",
                               "Weight digests are not attested by governed model receipts."]}
    write_payload_with_diff_ledger(OUTPUT, payload)
    print(json.dumps({"output": str(OUTPUT), "observed_result": payload["observed_result"],
                      "tests": len(tests), "elapsed_seconds": elapsed}, indent=2))
    return 0 if passed else result.returncode or 1


def _case_evidence(path: Path) -> dict:
    try:
        return _database_evidence(path)
    except sqlite3.OperationalError as exc:
        return {"database": str(path), "observed_result": "failure", "error": str(exc)}


def _server_metadata(base_url: str) -> dict:
    try:
        response = httpx.get(base_url.removesuffix("/v1").rstrip("/") + "/props", timeout=10)
        response.raise_for_status()
        props = response.json()
        template = str(props.get("chat_template") or "")
        return {"build_info": props.get("build_info"), "model_alias": props.get("model_alias"),
                "generation_settings": props.get("default_generation_settings"),
                "model_path": props.get("model_path"), "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
                "chat_template": template, "template_caps": props.get("chat_template_caps")}
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}


if __name__ == "__main__":
    raise SystemExit(main())
