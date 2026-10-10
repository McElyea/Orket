#!/usr/bin/env python3
"""Run a gardener report dispatch as a governed Orket agent run.

gardener (https://github.com/Stephenson-Software/gardener) can hand each
dispatch to a configured command instead of Claude Code. This script is that
command for Orket. It implements gardener's command-harness contract
(gardener docs/HARNESSES.md): the prompt arrives on stdin, the mode and spec in
``GARDENER_HARNESS_*`` environment variables, and one JSON object is printed on
stdout.

Only report mode is served. The repository is never handed to the model as
tools: a bounded snapshot (files the prompt names, then the repository's own
docs, then its file listing) becomes the run's authoritative context, and the
``repository-audit`` workload in ``extension/`` returns an advisory report that
Orket's advisory-report verifier must accept before the run completes.

This is a standalone command-line process, never imported by the Orket
runtime, so it uses blocking subprocess and file calls.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from orket_extension_sdk import canonical_json
from orket_extension_sdk.agent_fixtures import agent_iteration_request, agent_model_profile_request, prefixed_digest

EXTENSION_ROOT = Path(__file__).resolve().parent / "extension"
WORKLOAD_ID = "repository-audit"
PROVIDERS = ("ollama", "llama_cpp", "lmstudio", "openai_compat", "fixture")
DEFAULT_DOCS = "README.md,CLAUDE.md,AGENTS.md,CONTRIBUTING.md,SECURITY.md"
# Submit errors that say this device's model or provider is unavailable, so every
# repository in a gardener overnight batch would fail the same way.
DEVICE_UNAVAILABLE_ERRORS = ("E_AGENT_LOCAL_MODEL_UNAVAILABLE", "E_AGENT_LOCAL_INVENTORY_UNAVAILABLE")
_PATH_PATTERN = re.compile(r"(?<![\w.-])(/[^\s`'\"()<>]+)")


def setting(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def int_setting(name: str, default: int) -> int:
    raw = setting(name)
    value = int(raw) if raw else default
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def emit(result: str, *, is_error: bool, session_id: str | None = None, blocked: bool = False) -> None:
    print(json.dumps({
        "result": result, "is_error": is_error, "session_id": session_id,
        "total_cost_usd": 0, "permission_denials": [], "blocked": blocked,
    }))


def materialized(reference: str, kind: str, content: object) -> dict:
    encoded = canonical_json(content).encode("utf-8")
    return {"reference": reference, "kind": kind, "media_type": "application/json", "encoding": "json",
            "digest": prefixed_digest(content), "encoded_bytes": len(encoded), "content": content,
            "provenance_refs": [f"provenance:{reference}"]}


def _read_head(path: Path, limit: int) -> str | None:
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    text = data[:limit].decode("utf-8", errors="replace")
    return text + ("\n[truncated]" if len(data) > limit else "")


def collect_sources(prompt: str, repo: Path, roots: list[Path]) -> dict[str, dict]:
    """Bounded snapshot: prompt-named files, then repository docs, then the listing."""
    per_file = int_setting("ORKET_GARDENER_MAX_FILE_BYTES", 6_000)
    budget = int_setting("ORKET_GARDENER_MAX_TOTAL_BYTES", 24_000)
    allowed = [repo.resolve(), *(root.resolve() for root in roots)]
    candidates: list[Path] = []
    for match in _PATH_PATTERN.findall(prompt):
        path = Path(match.rstrip(".,:;"))
        if any(path.resolve().is_relative_to(root) for root in allowed):
            candidates.append(path)
    candidates += [repo / name for name in setting("ORKET_GARDENER_DOCS", DEFAULT_DOCS).split(",") if name.strip()]
    sources: dict[str, dict] = {}
    used = 0
    for path in dict.fromkeys(candidate.resolve() for candidate in candidates):
        if not path.is_file() or used >= budget:
            continue
        text = _read_head(path, min(per_file, budget - used))
        if text is None:
            continue
        label = str(path.relative_to(repo.resolve())) if path.is_relative_to(repo.resolve()) else str(path)
        # Short opaque references: a small model echoes every source_ref it
        # cites, and long absolute paths alone can exhaust a 512-token cap.
        sources[f"src{len(sources) + 1:02d}"] = {"path": label, "text": text}
        used += len(text.encode("utf-8"))
    sources["listing"] = {"path": "git ls-files", "files": _tracked_files(repo)}
    return sources


def _tracked_files(repo: Path) -> list[str]:
    limit = int_setting("ORKET_GARDENER_MAX_FILES", 400)
    try:
        listing = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True, text=True,
                                 timeout=60, check=True).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return []
    return listing[:limit] + ([f"[{len(listing) - limit} more not shown]"] if len(listing) > limit else [])


def build_request(prompt: str, sources: dict[str, dict], now: datetime, timeout_s: int) -> dict:
    request = agent_iteration_request()
    run_id = f"gardener-{uuid.uuid4().hex[:12]}"
    request["identity"].update(run_id=run_id, trace_id=run_id)
    request["objective_ref"] = "objective:gardener-report"
    request["acceptance_ref"] = "acceptance:advisory-report-v1"
    request["authoritative_context_refs"] = list(sources)
    request["materialized_inputs"] = [
        materialized(request["objective_ref"], "objective", {"task": prompt}),
        materialized(request["acceptance_ref"], "acceptance", {"required": ["report", "source_refs"]}),
        *(materialized(ref, "authoritative_context", content) for ref, content in sources.items()),
    ]
    request["admitted_capabilities"] = ["agent.iteration.v1"]
    profile = agent_model_profile_request()
    profile.update(role="auditor", profile_ref="local.auditor",
                   max_input_tokens=int_setting("ORKET_GARDENER_MAX_INPUT_TOKENS", 8_192),
                   max_output_tokens=int_setting("ORKET_GARDENER_MAX_OUTPUT_TOKENS", 2_048),
                   timeout_ms=timeout_s * 1000)
    request["model_profiles"] = [profile]
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        budget = request[scope]
        budget.update(iterations=1, model_calls=2, repair_attempts=1, wall_time_ms=timeout_s * 1000,
                      input_tokens=2 * profile["max_input_tokens"], output_tokens=2 * profile["max_output_tokens"],
                      effect_proposals=0, per_capability_effects=[],
                      per_role_model_calls=[{"role": "auditor", "count": 2}],
                      per_role_inference_concurrency=[{"role": "auditor", "count": 1}])
        budget.pop("snapshot_digest", None)
        budget["snapshot_digest"] = prefixed_digest(budget)
    request["deadline_utc"] = (now + timedelta(seconds=timeout_s)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(seconds=timeout_s - 1)).isoformat()
    # The host's local prompt profile can cap structured output well below the
    # request (512 tokens for Ollama Llama models), so the report is kept short.
    request["extension_config"] = {"report_word_limit": int_setting("ORKET_GARDENER_REPORT_WORDS", 250)}
    return request


def write_catalog(area: Path) -> None:
    manifest_path = EXTENSION_ROOT / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog = {"extensions": [{
        "extension_id": manifest["extension_id"], "extension_version": manifest["extension_version"],
        "extension_api_version": "1.0.0", "source": "gardener-harness-example", "path": str(EXTENSION_ROOT),
        "contract_style": "sdk_v0", "manifest_path": str(manifest_path),
        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"], "manifest_entries": manifest["workloads"],
    }]}
    (area / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")


def provider_args(provider: str, model: str) -> list[str]:
    if provider == "fixture":
        return ["--deterministic-fixture"]
    if not model:
        raise ValueError("no model: set GARDENER_HARNESS_MODEL (gardener --model) for a live provider")
    args = ["--provider", provider, "--model", model]
    if base_url := setting("ORKET_GARDENER_PROVIDER_BASE_URL"):
        args += ["--provider-base-url", base_url]
    return args


def submit(area: Path, request: dict, now: datetime, provider: list[str], timeout_s: int) -> dict:
    (area / "request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    write_catalog(area)
    argv = [setting("ORKET_GARDENER_ORKET_BIN", "orket"), "agent", "submit", WORKLOAD_ID,
            "--db", str(area / "agent.sqlite3"), "--catalog", str(area / "catalog.json"),
            "--request", str(area / "request.json"), "--creation-timestamp-utc", now.isoformat(),
            "--decision-timestamp-utc", (now + timedelta(seconds=1)).isoformat(), *provider, "--json"]
    proc = subprocess.run(argv, cwd=area, capture_output=True, text=True, timeout=timeout_s + 60,
                          env={**os.environ, "ORKET_DISABLE_SANDBOX": "1"})
    (area / "submit.json").write_text(proc.stdout, encoding="utf-8")
    (area / "submit.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "error": (proc.stderr or proc.stdout).strip()[-2000:] or "no output"}
    return payload if isinstance(payload, dict) else {"ok": False, "error": "unexpected submit output"}


def failure_reason(payload: dict) -> str:
    if payload.get("error"):
        return str(payload["error"])
    truth = payload.get("final_truth") or {}
    rules = [decision.get("rule") for decision in payload.get("decisions") or []]
    calls = [call.get("result", {}).get("normalized_reason") or call.get("status")
             for iteration in payload.get("iterations") or [] for call in iteration.get("model_calls") or []]
    return (f"final truth {truth.get('result_class')}/{truth.get('completion_classification')}, "
            f"decision rules {rules}, model calls {calls}")


def render(payload: dict, area: Path, sources: dict[str, dict]) -> tuple[str, bool]:
    result = payload.get("authoritative_result") or {}
    if not payload.get("ok") or not isinstance(result.get("advisory_proposal"), str):
        return f"Orket run did not produce a verified report: {failure_reason(payload)}\nRun area: {area}", True
    report = json.loads(result["advisory_proposal"])
    cited = ", ".join(f"{ref} ({sources.get(ref, {}).get('path', '?')})" for ref in report["source_refs"])
    footer = (f"\n\n---\nOrket run `{payload['run']['run_id']}` ({payload.get('proof_posture')}), "
              f"verified by the advisory-report verifier; sources: {cited}.\n"
              f"Inspect: orket agent inspect {payload['run']['run_id']} --db {area / 'agent.sqlite3'} --json")
    return report["report"] + footer, False


def main() -> int:
    prompt = sys.stdin.read()
    mode = setting("GARDENER_HARNESS_MODE")
    if mode != "report":
        emit(f"the Orket gardener harness serves report mode only, not {mode!r}", is_error=True)
        return 2
    try:
        spec = json.loads(setting("GARDENER_HARNESS_SPEC", "{}"))
        provider = setting("ORKET_GARDENER_PROVIDER", "ollama")
        if provider not in PROVIDERS:
            raise ValueError(f"ORKET_GARDENER_PROVIDER must be one of {', '.join(PROVIDERS)}")
        timeout_s = int_setting("GARDENER_HARNESS_TIMEOUT", 1_800)
        args = provider_args(provider, setting("GARDENER_HARNESS_MODEL"))
    except ValueError as exc:
        emit(f"configuration error: {exc}", is_error=True)
        return 2
    now = datetime.now(UTC)
    work = Path(setting("ORKET_GARDENER_WORK_DIR", str(Path.home() / ".orket" / "gardener-harness")))
    area = work / f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    area.mkdir(parents=True)
    sources = collect_sources(prompt, Path.cwd(), [Path(item) for item in spec.get("add_dirs", [])])
    request = build_request(prompt, sources, now, timeout_s)
    try:
        payload = submit(area, request, now, args, timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        emit(f"could not run orket: {exc}", is_error=True, blocked=isinstance(exc, FileNotFoundError))
        return 1
    text, failed = render(payload, area, sources)
    blocked = failed and str(payload.get("error") or "").startswith(DEVICE_UNAVAILABLE_ERRORS)
    emit(text, is_error=failed, session_id=f"orket:{request['identity']['run_id']}", blocked=blocked)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
