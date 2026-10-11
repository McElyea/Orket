#!/usr/bin/env python3
"""Standalone Gardener command harness; report-only, committed snapshots, owned commands.

Run with the Python that has Orket installed. The extension remains the canonical
public-SDK report example; this CLI adapter does not add a completion verifier.
Blocking file and console operations belong exclusively to this native CLI.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from gardener_scope import inventory_payload, relative_scope
from gardener_snapshot import Commands, HarnessFailure, collect_sources, verify_unchanged
from gardener_submission import accepted_report, failure_reason, prepare_submission, token_limits

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_PROVIDER, PROVIDER_CHOICES

UNAVAILABLE = ("E_AGENT_LOCAL_MODEL_UNAVAILABLE", "E_AGENT_LOCAL_INVENTORY_UNAVAILABLE",
               "E_AGENT_LOCAL_MODEL_REQUIRED", "E_AGENT_MODEL_PROVIDER_UNAVAILABLE", "E_AGENT_MODEL_PROVIDER_TIMEOUT")


def configuration(environment: dict[str, str], root: Path) -> tuple[dict, list[Path], Path, Path, int]:
    if environment.get("GARDENER_HARNESS_MODE") != "report":
        raise HarnessFailure("the Orket Gardener harness serves report mode only")
    spec = json.loads(environment.get("GARDENER_HARNESS_SPEC", "{}"))
    if (not isinstance(spec, dict) or spec.get("merge_allowed") is not False
            or spec.get("permission_mode") != "plan" or spec.get("mode", "report") != "report"
            or set(spec.get("tools", [])) - {"Read", "Grep", "Glob"} or spec.get("allowed_tools", [])):
        raise HarnessFailure("report spec must allow only Read/Grep/Glob, plan mode, and no merge or commands")
    dirs = spec.get("add_dirs", [])
    if not isinstance(dirs, list) or len(dirs) > 8 or any(not isinstance(item, str) or not item for item in dirs):
        raise HarnessFailure("add_dirs must contain at most eight explicit source directories")
    roots = [(root / item).resolve(strict=True) for item in dirs]
    if subdir := environment.get("ORKET_GARDENER_CONVENTIONS_SUBDIR"):
        scope = relative_scope(subdir)
        selected = [(path / str(scope)).resolve(strict=True) for path in roots]
        if any(not child.is_relative_to(parent) for parent, child in zip(roots, selected, strict=True)):
            raise HarnessFailure("conventions subdirectory escapes its declared source root")
        roots = selected
    timeout = int(environment.get("GARDENER_HARNESS_TIMEOUT", "1800"))
    if not 30 <= timeout <= 3600:
        raise HarnessFailure("GARDENER_HARNESS_TIMEOUT must be between 30 and 3600 seconds", blocked=True)
    provider = environment.get("ORKET_GARDENER_PROVIDER", DEFAULT_LOCAL_PROVIDER).strip()
    model = environment.get("GARDENER_HARNESS_MODEL", "").strip()
    if provider not in PROVIDER_CHOICES or not model:
        raise HarnessFailure("select a supported provider and set GARDENER_HARNESS_MODEL", blocked=True)
    catalog_value = environment.get("ORKET_GARDENER_CATALOG", "").strip()
    if not catalog_value:
        raise HarnessFailure("ORKET_GARDENER_CATALOG must name the installed report extension catalog", blocked=True)
    catalog = (root / catalog_value).resolve(strict=True)
    work = Path(environment.get("ORKET_GARDENER_WORK_DIR", str(Path.home() / ".orket/gardener-harness"))).resolve()
    if work.is_relative_to(root) or any(work.is_relative_to(path) for path in roots):
        raise HarnessFailure("ORKET_GARDENER_WORK_DIR must be outside the source directories")
    return {"provider": provider, "model": model}, roots, catalog, work, timeout


def execute(prompt: str, environment: dict[str, str], root: Path) -> dict:
    selection, roots, catalog, work, timeout = configuration(environment, root)
    input_tokens, output_tokens = token_limits(environment)
    # Leave Gardener time to observe settlement and receive the final envelope.
    commands = Commands(work, {**environment, "ORKET_DISABLE_SANDBOX": "1", "PYTHONIOENCODING": "utf-8"},
                        time.monotonic() + timeout - 15)
    sources, trees = collect_sources(commands, prompt, root, roots)
    work.mkdir(parents=True, exist_ok=True)
    area = Path(tempfile.mkdtemp(prefix="run-", dir=work))
    (area / "snapshot-inventory.json").write_text(json.dumps(inventory_payload(trees)), encoding="utf-8")
    commands.area = area
    commands.owner = commands.owner.for_workspace(area)
    remaining = int(commands.deadline - time.monotonic()) - 5
    if remaining < 1:
        raise HarnessFailure("snapshot consumed the report time budget", blocked=True)
    submission, inputs = prepare_submission(area, prompt, sources, remaining,
        input_tokens=input_tokens, output_tokens=output_tokens)
    database = area / "agent.sqlite3"
    argv = [sys.executable, "-m", "orket.cli", "agent", "run", "--submission", str(submission),
            "--inputs", str(inputs), "--catalog", str(catalog), "--db", str(database),
            "--provider", selection["provider"], "--model", selection["model"], "--json"]
    if endpoint := environment.get("ORKET_GARDENER_PROVIDER_BASE_URL"):
        argv.extend(["--provider-base-url", endpoint])
    result = commands.run(argv, area)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise HarnessFailure(f"invalid Orket result; retained run area: {area}")
    run_id = (payload.get("run") or {}).get("run_id")
    inspect = f'orket agent inspect "{run_id}" --db "{database}" --json' if run_id else str(area)
    if result.returncode != 0 or payload.get("ok") is not True:
        error = failure_reason(payload)
        raise HarnessFailure(f"{error}; inspect retained run: {inspect}",
                             blocked=error.startswith(UNAVAILABLE), run_id=run_id)
    if not isinstance(run_id, str) or not run_id:
        raise HarnessFailure(f"Orket success omitted its run identity; retained run area: {area}")
    try:
        report = accepted_report(payload, sources)
        verify_unchanged(commands, trees)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        raise HarnessFailure(f"{exc}; inspect retained run: {inspect}", run_id=run_id,
                             blocked=isinstance(exc, HarnessFailure) and exc.blocked) from exc
    footer = (f"\n\n---\nAdvisory report; verified delivery and source references only. "
              f"Committed snapshots only; no tests or fixes executed.\n"
              f"Requested token limits: input {input_tokens}, output {output_tokens}; host limits also enforced.\n"
              f"Run: {run_id}\nDatabase: {database}\n"
              f"Inspect: orket agent inspect \"{run_id}\" --db \"{database}\" --json")
    return {"result": report + footer, "is_error": False, "session_id": f"orket:{run_id}",
            "total_cost_usd": None, "permission_denials": [], "blocked": False}


def main() -> int:
    try:
        prompt = sys.stdin.read(65_537)
        if not prompt.strip() or len(prompt.encode("utf-8")) > 65_536:
            raise HarnessFailure("prompt must contain 1 to 65536 UTF-8 bytes")
        envelope = execute(prompt, dict(os.environ), Path.cwd().resolve())
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        envelope = {"result": f"Orket Gardener report failed: {exc}", "is_error": True,
                    "session_id": (f"orket:{exc.run_id}" if isinstance(exc, HarnessFailure) and exc.run_id else None),
                    "total_cost_usd": None, "permission_denials": [],
                    "blocked": isinstance(exc, HarnessFailure) and exc.blocked}
    print(json.dumps(envelope, ensure_ascii=True))
    return 1 if envelope["is_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
