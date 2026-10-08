"""Clean candidate inputs and independent package/effect observations for CI tooling."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.common.git_inventory import git_list_files

MISSING_PROVIDER_MODEL = "acceptance-model"


def require_missing_provider_refusal(setup: dict[str, Any]) -> None:
    """Admit the held-loopback connection refusal, not an unrelated diagnostic failure."""
    diagnostic = setup["missing_provider"]
    endpoint = setup["missing_provider_endpoint"]
    address = urlsplit(endpoint)
    observed, command = diagnostic["provider_observation"], diagnostic["command_observation"]
    # This is the observed HTTP connection-failure vocabulary, not every error
    # wrapped by provider preparation. A changed message requires investigation.
    expected_error = ("ModelConnectionError: Provider runtime preparation failed provider=llama_cpp "
                      f"requested_model={MISSING_PROVIDER_MODEL}: All connection attempts failed")
    if (address.scheme != "http" or address.hostname != "127.0.0.1" or not address.port
            or address.path != "/v1" or address.username or address.password or address.query or address.fragment
            or diagnostic["project"] != setup["project"] or diagnostic["base_url"] != endpoint
            or diagnostic["provider"] != "llama_cpp" or diagnostic["model"] != MISSING_PROVIDER_MODEL
            or diagnostic["ok"] is not False or diagnostic["observed_path"] != "primary"
            or diagnostic["observed_result"] != "failure" or observed["catalog_admitted"] is not False
            or observed.get("error") != expected_error or observed["resources_closed"] is not True
            or observed["inference"] != "not_established" or command["ok"] is not True
            or command["returncode"] != 0 or command["reason"] != "completed"
            or command["cleanup_confirmed"] is not True or command["capture_complete"] is not True):
        raise ValueError("Missing-provider evidence requires the held endpoint's connection failure and settled diagnostics")


def file_identity(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def snapshot_packages(repo: Path, destination: Path) -> dict[str, Any]:
    """Copy only Git-visible authored inputs; never reuse a build/egg-info cache."""
    excluded = {"build", "dist", "__pycache__", ".venv", "node_modules"}
    inputs = {}
    for path in git_list_files(repo):
        relative = path.relative_to(repo)
        if relative.parts[0] not in {"orket", "orket_extension_sdk", "pyproject.toml", "README.md", "LICENSE"}:
            continue
        if any(part in excluded or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        content = path.read_bytes()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        inputs[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    required = {"pyproject.toml", "README.md", "LICENSE", "orket/__init__.py",
                "orket_extension_sdk/pyproject.toml", "orket_extension_sdk/__init__.py"}
    if not required.issubset(inputs):
        raise ValueError(f"Incomplete candidate source: {sorted(required - inputs.keys())}")
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    return {"sha256": digest, "paths_count": len(inputs), "inputs": inputs}


def inspect_wheel(path: Path, source: Path, namespace: str) -> dict[str, Any]:
    """Compare built package bytes with captured sources and forbid namespace overlap."""
    other = "orket_extension_sdk" if namespace == "orket" else "orket"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if any(name.startswith(other + "/") for name in names):
            raise ValueError(f"Wheel bundles the other distribution's namespace: {path.name}")
        for name in names:
            if name.startswith(namespace + "/") and not name.endswith("/"):
                authored = source / name
                if not authored.is_file() or archive.read(name) != authored.read_bytes():
                    raise ValueError(f"Wheel/source bytes differ: {name}")
        required = {f"{namespace}/__init__.py"}
        if namespace == "orket":
            # All package resources must survive the clean build, not just one chosen fixture.
            required.update(p.relative_to(source).as_posix() for p in (source / namespace).rglob("*")
                            if p.is_file() and p.suffix not in {".py", ".pyc"})
        else:
            required.add("orket_extension_sdk/py.typed")
            required.update(p.relative_to(source).as_posix()
                            for p in (source / namespace / "schemas").glob("*.json"))
        required.update(p.relative_to(source).as_posix() for p in (source / namespace).rglob("*.py")
                        if "build" not in p.relative_to(source / namespace).parts)
        if not required.issubset(names):
            raise ValueError(f"Wheel missing authored package files: {sorted(required - names)}")
    return {**file_identity(path), "namespace": namespace, "required_files_checked": len(required)}


def observe_quickstart(project: Path, decision: str) -> dict[str, Any]:
    """Observe actual files and terminal ledger values independently of printed success."""
    output = project / "quickstart_out/hello_from_orket.txt"
    if decision == "approve":
        # The existing quickstart contract is UTF-8 text with native newline translation.
        # Retain the byte hash below independently, including the actual Windows CRLF.
        if output.read_text(encoding="utf-8") != "hello from a governed Orket action\n":
            raise ValueError("Approved quickstart did not produce the declared text")
    elif output.exists():
        raise ValueError("Denied quickstart created its forbidden output")
    ledgers = list((project / ".orket/quickstart/runs").glob("*/ledger.jsonl"))
    if len(ledgers) != 1:
        raise ValueError("Expected exactly one quickstart ledger in a fresh project")
    ledger = ledgers[0]
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    expected = "approved_executed" if decision == "approve" else "denied_skipped"
    if rows[-1]["event_type"] != "run_finished" or rows[-1]["payload"]["terminal_status"] != expected:
        raise ValueError("Quickstart terminal ledger does not match the requested decision")
    return {"decision": decision, "ledger": file_identity(ledger), "terminal_status": expected,
            "output": file_identity(output) if output.exists() else None}
