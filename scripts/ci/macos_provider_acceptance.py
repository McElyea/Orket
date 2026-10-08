"""Owned local server and installed public workflow for the native acceptance producer."""
from __future__ import annotations

import asyncio
import hashlib
import json
import socket
from pathlib import Path

import httpx
from dotenv import dotenv_values

from orket.application.services.command_process_supervisor import CommandProcessCancelled
from scripts.ci.candidate_install_support import file_identity, observe_quickstart
from scripts.ci.macos_acceptance_evidence import metal_log_observation
from scripts.common.evidence_environment import utc_now_iso
from scripts.proof.run_governed_agent_acceptance import _database_evidence


def pass_case(run, identity: str, evidence: dict) -> None:
    run.payload["cases"][identity] = {"status": "PASS", "evidence": evidence}
    run.save()


def large_file_identity(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


async def await_server(run, operation, endpoint: str) -> None:
    async with asyncio.timeout(120), httpx.AsyncClient(timeout=2, trust_env=False) as client:
        while not operation.done():
            try:
                response = await client.get(endpoint + "/health")
                if response.status_code == 200:
                    props = await client.get(endpoint + "/props")
                    props.raise_for_status()
                    run.payload["server"]["props"] = props.json()
                    run.save()
                    return
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass  # Bounded startup wait; failure/exit remains visible in retained server evidence.
            await asyncio.sleep(0.5)
    raise RuntimeError("Owned llama.cpp server ended before readiness")


async def guided_setup(run, python: Path, model: Path, alias: str, endpoint: str) -> Path:
    project = run.area / "guided project café"
    cli = python.parent / ("orket.exe" if python.suffix == ".exe" else "orket")
    # Exercise the published interactive wizard, including the explicit approval.
    answers = ["Mac acceptance", "Verify the installed candidate", "Truthful observations",
               "workspace", "model", "developer-local", "llama_cpp", alias, endpoint + "/v1", str(model.parent), "approve"]
    supplied = ("\n".join(answers) + "\n").encode("utf-8")
    run.payload["active_case"] = "MA-02"
    await run.command([str(cli), "setup", "--project", str(project), "--run-example"], cwd=run.area,
                       input_data=supplied, timeout_seconds=150)
    organization = json.loads((project / "config/organization.json").read_text(encoding="utf-8"))
    environment = dotenv_values(project / ".env", interpolate=False)
    if (organization["name"] != answers[0] or organization["process_rules"]["default_llm"] != alias
            or environment["ORKET_LLM_PROVIDER"] != "llama_cpp"
            or environment["ORKET_LLM_LLAMA_CPP_BASE_URL"] != endpoint + "/v1"
            or await asyncio.to_thread(Path(environment["ORKET_LLAMA_CPP_GGUF_MODEL_ROOT"]).resolve) != model.parent):
        raise ValueError("Guided setup did not retain the selected project/provider/model")
    quickstart = observe_quickstart(project / "workspace", "approve")
    await run.command([str(python), "-I", "-m", "orket.quickstart.verify_ledger", quickstart["ledger"]["path"]], cwd=run.area)
    pass_case(run, "MA-02", {"project": str(project), "organization": file_identity(project / "config/organization.json"),
                             "dotenv": file_identity(project / ".env"), "quickstart": quickstart,
                             "stdin_sha256": hashlib.sha256(supplied).hexdigest()})
    return project


async def actual_workflow(run, python: Path, project: Path, alias: str) -> None:
    cli = python.parent / ("orket.exe" if python.suffix == ".exe" else "orket")
    run.payload["active_case"] = "MA-04"
    raw = await run.command([str(cli), "demo", "local-agent", "--project", str(project), "--json"],
                            cwd=run.area, timeout_seconds=650)
    payload = json.loads(raw)
    if (not payload["ok"] or payload["proof_posture"] != "live_local_model"
            or payload["run"]["lifecycle_state"] != "completed"
            or [item["disposition"] for item in payload["decisions"]] != ["continue", "complete"]):
        raise ValueError("Actual provider workflow did not reach verified completion")
    db = Path(payload["db_path"])
    # Reuse the read-only SQLite observer; omit its older API-harness concurrency attribution.
    observed = {key: value for key, value in _database_evidence(db).items()
                if key not in {"peak_admitted_concurrency", "concurrency_basis"}}
    proposal = json.loads(observed["iterations"][-1]["proposal"])
    receipts = observed["receipts"]
    if (proposal["counts"] != {"open": 2, "closed": 2, "blocked": 1}
            or proposal["source_refs"] != ["artifact:ticket-batch-a", "artifact:ticket-batch-b"]
            or len(receipts) < 6 or any(item["provider"] != "llama_cpp" or item["model"] != alias
                or item["usage_posture"] != "measured" or item["status"] != "returned" for item in receipts)):
        raise ValueError("Independent workflow result or actual model receipts do not match")
    if (set(payload["model_targets"]) != {"planner", "actor", "critic"}
            or any(target["base_url"] != run.payload["server"]["endpoint"] + "/v1"
                   for target in payload["model_targets"].values())):
        raise ValueError("Workflow did not use the acceptance-owned server")
    pass_case(run, "MA-04", {"database": observed, "command_output": run.payload["commands"][-1]["stdout"],
                             "server_identity": run.payload["server"]["executable"], "model": run.payload["server"]["model"]})
    run.payload["active_case"] = "MA-08"
    before = file_identity(db)
    results = {}
    for command in ("inspect", "replay"):
        value = json.loads(await run.command([str(cli), "agent", command, "run-1", "--db", str(db), "--json"], cwd=run.area))
        if not value["ok"] or (command == "replay" and value["status"] != "matched"):
            raise ValueError("Fresh-process retained workflow inspection/replay failed")
        results[command] = run.payload["commands"][-1]["stdout"]
    diagnostic = json.loads(await run.command([str(cli), "doctor", "--project", str(project), "--json"], cwd=run.area))
    if (file_identity(db) != before or not diagnostic["ok"] or diagnostic["model"] != alias
            or " " not in project.name or not any(ord(c) > 127 for c in project.name)):
        raise ValueError("Restart changed retained state or failed to load saved Unicode-path inputs")
    hardware = diagnostic["hardware"]
    if run.payload["native_mac"] and (hardware["memory_model"] != "unified"
            or hardware["vram_gb_used"] is not None or hardware["vram_total_gb"] is not None
            or hardware["unified_memory_gb"] <= 0 or hardware["gpu_observation"] != "metal_unverified"):
        raise ValueError("Native hardware diagnostic conflated unified memory with dedicated GPU observations")
    pass_case(run, "MA-08", {"database": before, "fresh_processes": results, "diagnostic": diagnostic})


async def stop_server(run, operation, port: int) -> None:
    operation.cancel()
    try:
        result = await operation
        interrupted = False
    except CommandProcessCancelled as exc:
        result, interrupted = exc.lifetime, True
    record = run.payload["server"]
    record.update(returncode=result.returncode, lifetime=result.lifetime(), cancelled=interrupted, finished_at_utc=utc_now_iso())
    for name, content in (("stdout", result.stdout), ("stderr", result.stderr)):
        path = run.area / f"llama-server.{name}.log"
        path.write_bytes(content)
        record[name] = file_identity(path)
    with socket.socket() as observer:
        observer.settimeout(1)
        record["port_closed_after_settlement"] = observer.connect_ex(("127.0.0.1", port)) != 0
    run.save()
    if not result.cleanup_confirmed or not result.capture_complete or not record["port_closed_after_settlement"]:
        raise RuntimeError("Acceptance server teardown or capture is uncertain")
    metal = metal_log_observation((result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace"))
    native = run.payload["native_mac"]
    proved = native and run.payload["cases"]["MA-04"]["status"] == "PASS" and metal["metal_model_allocation_observed"]
    run.payload["cases"]["MA-05"] = {"status": "PASS" if proved else "BLOCKED" if not native else "FAIL",
        "evidence": metal, "reason": "Native Metal execution required; CPU/Windows or allocation without inference cannot substitute"}
    run.save()


async def exercise_provider(run, python: Path, server: Path, model: Path, alias: str) -> None:
    run.payload["active_case"] = "MA-04"
    if not await asyncio.to_thread(server.is_file) or not await asyncio.to_thread(model.is_file):
        raise ValueError("Prepared llama.cpp executable and GGUF model paths are required")
    installed = run.payload["observations"]["installed"]
    core, = [item for item in installed["distributions"] if item["name"] == "orket"]
    template = Path(core["origin"]).parent / "runtime/config/qwen38_text_chatml.jinja"
    with socket.socket() as selected:
        selected.bind(("127.0.0.1", 0))
        port = selected.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    argv = [str(server), "--model", str(model), "--alias", alias, "--host", "127.0.0.1", "--port", str(port),
            "--n-gpu-layers", "99", "--flash-attn", "on", "--ctx-size", "8192", "--parallel", "1",
            "--jinja", "--reasoning", "off", "--cache-prompt", "--cache-ram", "8192", "--chat-template-file", str(template)]
    run.payload["server"] = {"argv": argv, "cwd": str(run.area), "endpoint": endpoint, "timeout_seconds": 900,
                              "started_at_utc": utc_now_iso(), "executable": file_identity(server),
                              "model": await asyncio.to_thread(large_file_identity, model), "template": file_identity(template)}
    run.save()
    await run.command([str(server), "--version"], cwd=run.area)
    run.payload["server"]["version_log"] = run.payload["commands"][-1]["stdout"]
    run.save()
    operation = asyncio.create_task(run.owner.run(argv, cwd=run.area, environment=run.environment,
                                                 timeout_seconds=900, output_limit_bytes=16 * 1024 * 1024))
    try:
        await await_server(run, operation, endpoint)
        project = await guided_setup(run, python, model, alias, endpoint)
        await actual_workflow(run, python, project, alias)
        if operation.done():
            raise RuntimeError("Owned server exited before the acceptance workflow settled")
    finally:
        await stop_server(run, operation, port)
