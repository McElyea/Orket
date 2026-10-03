"""Record actual TD03052026 Quality command outcomes; no caller-supplied verdicts."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from scripts.common.evidence_environment import utc_now_iso
from scripts.common.git_inventory import GitInventoryError, git_list_files
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.governance.check_td03052026_gate_audit import GATE_IDS, READINESS_PREREQS, REQUIRED_CI_SNIPPETS

DEFAULT_ROOT = Path("benchmarks/results/techdebt/td03052026")
SOURCE_PREFIXES = ("orket/", "orket_extension_sdk/", "scripts/", "tests/", "docs/", ".gitea/")
# This second command belongs to the existing Quality provider-close step.
PROVIDER_CLOSE_EXTRA = "python -m pytest -q tests/adapters/test_local_model_provider_telemetry.py -k close_is_idempotent"


def gate_commands(gate_id: str) -> list[list[str]]:
    commands = [shlex.split(REQUIRED_CI_SNIPPETS[gate_id])]
    if gate_id == "G4":
        commands.append(shlex.split(PROVIDER_CLOSE_EXTRA))
    return commands


def source_identity(repo_root: Path) -> dict[str, Any]:
    commit = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                            capture_output=True, check=True).stdout.decode().strip()
    files = {}
    for path in git_list_files(repo_root):
        relative_path = path.relative_to(repo_root)
        relative = relative_path.as_posix()
        if any(part in {"node_modules", ".venv"} for part in relative_path.parts):
            continue
        if len(relative_path.parts) == 1 or any(relative_path.is_relative_to(Path(prefix)) for prefix in SOURCE_PREFIXES):
            files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"commit": commit, "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_paths_count": len(files), "source_prefixes": list(SOURCE_PREFIXES),
            "source_scope": "Git-visible authored roots plus root files; includes nonignored untracked inputs"}


def _result_path(output_root: Path, gate_id: str) -> Path:
    return output_root / "quality_gates" / gate_id.lower() / "result.json"


def validate_result(path: Path, *, gate_id: str, source: dict[str, Any], run_id: str,
                    expected_commands: list[list[str]]) -> tuple[bool, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (payload.get("schema_version") != "td03052026.quality_command_result.v1"
                or payload.get("gate_id") != gate_id or payload.get("status") != "PASS"
                or payload.get("source") != source or payload.get("run_id") != run_id
                or payload.get("planned_commands") != expected_commands):
            return False, "missing, failed, or stale command evidence"
        commands = payload["commands"]
        if len(commands) != len(expected_commands):
            return False, "incomplete command group"
        for index, (record, expected) in enumerate(zip(commands, expected_commands, strict=True)):
            lifetime = record["lifetime"]
            if (record["command"] != expected or record["argv"] != [sys.executable, *expected[1:]]
                    or record["returncode"] != 0 or lifetime["reason"] != "completed"
                    or lifetime["cleanup_confirmed"] is not True or lifetime["capture_complete"] is not True):
                return False, "command failed or native settlement incomplete"
            for stream in ("stdout", "stderr"):
                log = path.parent / f"command-{index + 1}.{stream}.log"
                if record[stream]["path"] != log.resolve().as_posix():
                    return False, "unexpected retained log path"
                if hashlib.sha256(log.read_bytes()).hexdigest() != record[stream]["sha256"]:
                    return False, "retained log hash mismatch"
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False, "missing or invalid retained evidence"
    return True, "all canonical commands exited zero with complete native settlement and matching logs/source/run"


def refresh_dashboard(output_root: Path, source: dict[str, Any], run_id: str) -> dict[str, Any]:
    timestamp, gates = utc_now_iso(), {}
    for gate_id in GATE_IDS:
        path = _result_path(output_root, gate_id)
        valid, detail = (validate_result(path, gate_id=gate_id, source=source, run_id=run_id,
                                        expected_commands=gate_commands(gate_id))
                         if gate_id in READINESS_PREREQS else (False, "no current proof produced by this recorder"))
        gates[gate_id] = {"state": "green" if valid else "red", "detail": detail,
                          "evidence": [path.resolve().as_posix()] if valid else [], "updated_at_utc": timestamp}
    payload = {"schema_version": "td03052026.hardening_dashboard.v1", "updated_at_utc": timestamp,
               "source": source, "run_id": run_id, "gates": gates}
    write_payload_with_diff_ledger(output_root / "hardening_dashboard.json", payload)
    return payload


async def execute_commands(commands: list[list[str]], *, repo_root: Path, log_root: Path,
                           timeout_seconds: float) -> list[dict[str, Any]]:
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    owner = CommandProcessSupervisor(repo_root, cancellation_event="quality_gate_command_interrupted")
    records = []
    for index, command in enumerate(commands):
        argv = [sys.executable, *command[1:]]
        started = utc_now_iso()
        result = await owner.run(argv, cwd=repo_root, environment=environment,
                                 timeout_seconds=timeout_seconds, output_limit_bytes=64 * 1024 * 1024)
        record = {"command": command, "argv": argv, "returncode": result.returncode,
                  "started_at_utc": started, "finished_at_utc": utc_now_iso(), "lifetime": result.lifetime()}
        await asyncio.to_thread(log_root.mkdir, parents=True, exist_ok=True)
        for stream, content in (("stdout", result.stdout), ("stderr", result.stderr)):
            path = log_root / f"command-{index + 1}.{stream}.log"
            path.write_bytes(content)
            record[stream] = {"path": path.resolve().as_posix(), "sha256": hashlib.sha256(content).hexdigest()}
            text = content.decode("utf-8", errors="replace")
            print(text, end="", file=sys.stdout if stream == "stdout" else sys.stderr)
        records.append(record)
        if result.returncode != 0 or result.reason != "completed" or not result.cleanup_confirmed:
            break
    return records


async def record_gate(gate_id: str, *, repo_root: Path, output_root: Path, run_id: str,
                      timeout_seconds: float) -> int:
    source, planned = source_identity(repo_root), gate_commands(gate_id)
    result_path = _result_path(output_root, gate_id)
    payload = {"schema_version": "td03052026.quality_command_result.v1", "gate_id": gate_id,
               "status": "RUNNING", "source": source, "run_id": run_id, "planned_commands": planned,
               "commands": [], "observed_path": "primary", "observed_result": "partial success",
               "started_at_utc": utc_now_iso()}
    write_payload_with_diff_ledger(result_path, payload)
    refresh_dashboard(output_root, source, run_id)
    try:
        payload["commands"] = await execute_commands(planned, repo_root=repo_root, log_root=result_path.parent,
                                                     timeout_seconds=timeout_seconds)
        current = source_identity(repo_root)
        succeeded = (current == source and len(payload["commands"]) == len(planned)
                     and all(record["returncode"] == 0 and record["lifetime"]["reason"] == "completed"
                             and record["lifetime"]["cleanup_confirmed"] and record["lifetime"]["capture_complete"]
                             for record in payload["commands"]))
        payload.update(status="PASS" if succeeded else "FAIL", source_unchanged=current == source,
                       observed_result="success" if succeeded else "failure", finished_at_utc=utc_now_iso())
        write_payload_with_diff_ledger(result_path, payload)
        dashboard = refresh_dashboard(output_root, current, run_id)
        return 0 if dashboard["gates"][gate_id]["state"] == "green" else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        payload.update(status="FAIL", observed_result="failure", error=f"{type(exc).__name__}: {exc}",
                       finished_at_utc=utc_now_iso())
        write_payload_with_diff_ledger(result_path, payload)
        refresh_dashboard(output_root, source, run_id)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=READINESS_PREREQS, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path())
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--run-id", default="")
    # Match the existing hosted runner ceiling; outer CI job/admission limits remain authoritative.
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    supplied = args.command[1:] if args.command[:1] == ["--"] else args.command
    groups: list[list[str]] = [[]]
    for token in supplied:
        if token == "--next":
            groups.append([])
        else:
            groups[-1].append(token)
    if groups != gate_commands(args.gate):
        parser.error("command group must exactly match the existing canonical Quality commands")
    run_id = args.run_id or ":".join(os.environ.get(key, "") for key in
                                    ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB"))
    if not run_id.strip(":"):
        parser.error("a CI run identity or explicit --run-id is required")
    repo_root = args.repo_root.resolve(strict=True)
    output_root = args.output_root if args.output_root.is_absolute() else repo_root / args.output_root
    try:
        return asyncio.run(record_gate(args.gate, repo_root=repo_root, output_root=output_root.resolve(),
                                       run_id=run_id, timeout_seconds=args.timeout_seconds))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, GitInventoryError) as exc:
        print(f"Quality gate evidence failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
