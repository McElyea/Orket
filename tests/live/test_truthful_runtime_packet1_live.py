from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

import orket.runtime.execution_pipeline as execution_pipeline_module
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.exceptions import ExecutionFailed
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.run_summary import PACKET1_MISSING_TOKEN
from tests.live.test_runtime_stability_closeout_live import _live_enabled, _live_model
from tests.live.test_system_acceptance_pipeline import _write_core_assets

pytestmark = pytest.mark.end_to_end


def _read_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_bytes().decode("utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _run_roots(workspace: Path) -> list[Path]:
    runs_root = workspace / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


async def _run_command(*args: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def _ensure_ollama_alias(source_model: str, alias_model: str) -> None:
    show_code, _, _ = await _run_command("ollama", "show", alias_model)
    if show_code == 0:
        return
    copy_code, _, copy_stderr = await _run_command("ollama", "cp", source_model, alias_model)
    if copy_code != 0:
        raise AssertionError(f"failed to create ollama alias {alias_model}: {copy_stderr.strip()}")


async def _remove_ollama_alias(alias_model: str) -> None:
    await _run_command("ollama", "rm", alias_model)


def _write_illegal_transition_assets(root: Path, *, epic_id: str, environment_model: str) -> None:
    (root / "config").mkdir(parents=True, exist_ok=True)
    for directory in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / directory).mkdir(parents=True, exist_ok=True)

    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": "Packet1 Live Org",
                "vision": "Live proof",
                "ethos": "Truthful runtime proof",
                "branding": {"design_dos": []},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
                "departments": ["core"],
            }
        ),
        encoding="utf-8",
    )
    for dialect_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{dialect_name}.json").write_text(
            json.dumps(
                {
                    "model_family": dialect_name,
                    "dsl_format": "JSON",
                    "constraints": [],
                    "hallucination_guard": "None",
                }
            ),
            encoding="utf-8",
        )
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "ARCH",
                "summary": "lead_architect",
                "type": "utility",
                "description": (
                    "Return exactly one fenced JSON tool-call block and nothing else. "
                    "Use the tool update_issue_status with args {\"status\":\"done\"}. "
                    "Do not explain your answer."
                ),
                "tools": ["write_file", "update_issue_status"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps(
            {
                "name": "standard",
                "seats": {
                    "lead_architect": {"name": "Lead", "roles": ["lead_architect"]},
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": environment_model, "temperature": 0.0, "timeout": 300}),
        encoding="utf-8",
    )
    (root / "model" / "core" / "epics" / f"{epic_id}.json").write_text(
        json.dumps(
            {
                "id": epic_id,
                "name": epic_id,
                "type": "epic",
                "team": "standard",
                "environment": "standard",
                "description": "Packet1 failure boundary case",
                "params": {"model_overrides": {"lead_architect": environment_model}},
                "architecture_governance": {"idesign": False, "pattern": "Tactical"},
                "issues": [
                    {
                        "id": "ISSUE-B",
                        "summary": "Boundary proof issue",
                        "seat": "lead_architect",
                        "priority": "High",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


async def test_packet1_live_failure_run_omits_classification_without_primary_output(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live packet1 proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")

    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "packet1_failure_live.db")
    _write_illegal_transition_assets(
        root,
        epic_id="packet1_failure_live",
        environment_model=_live_model(),
    )

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    with pytest.raises(ExecutionFailed):
        await engine.run_card("packet1_failure_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_summary = _read_json(run_roots[0] / "run_summary.json")
    packet1 = run_summary["truthful_runtime_packet1"]

    print(
        "[live][packet1][failure-no-primary] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"primary_output_kind={packet1['provenance']['primary_output_kind']}"
    )
    assert run_summary["status"] == "failed"
    assert packet1["provenance"]["primary_output_kind"] == "none"
    assert packet1["classification"] == {"classification_applicable": False}
    assert "truth_classification" not in packet1["provenance"]


@pytest.mark.asyncio
async def test_packet1_live_emission_failure_uses_runtime_event_fallback(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live packet1 proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")

    async def _raise_summary_generation(**_kwargs):
        raise ValueError("forced live packet1 summary generation failure")

    monkeypatch.setattr(
        execution_pipeline_module,
        "generate_run_summary_for_finalize",
        _raise_summary_generation,
    )

    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "packet1_emission_failure_live.db")
    _write_core_assets(root, epic_id="packet1_emission_failure_live", environment_model=_live_model())

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("packet1_emission_failure_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_summary = _read_json(run_roots[0] / "run_summary.json")
    runtime_events = _read_jsonl(workspace / "agent_output" / "observability" / "runtime_events.jsonl")
    packet1_failure = next(event for event in runtime_events if event.get("event") == "packet1_emission_failure")

    print(
        "[live][packet1][emission-failure] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"fallback_status={packet1_failure['packet1_conformance']['status']}"
    )
    assert run_summary["status"] == "done"
    assert "truthful_runtime_packet1" not in run_summary
    assert packet1_failure["packet1_conformance"]["status"] == "non_conformant"
    assert packet1_failure["packet1_conformance"]["reasons"] == ["packet1_emission_failure"]


@pytest.mark.asyncio
async def test_packet1_live_fallback_profile_marks_degraded_truth(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live packet1 proof.")

    source_model = _live_model()
    alias_model = "packet1-fallback-proof:7b"
    await _ensure_ollama_alias(source_model, alias_model)

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_MODE", "enforce")
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID", "ollama.qwen.chatml.v1")

    try:
        root = tmp_path
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "agent_output").mkdir()
        (workspace / "verification").mkdir()
        db_path = str(root / "packet1_fallback_live.db")
        _write_core_assets(root, epic_id="packet1_fallback_live", environment_model=alias_model)

        engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
        await engine.run_card("packet1_fallback_live")

        run_roots = _run_roots(workspace)
        assert len(run_roots) == 1
        run_summary = _read_json(run_roots[0] / "run_summary.json")
        packet1 = run_summary["truthful_runtime_packet1"]

        print(
            "[live][packet1][fallback-profile] "
            f"run_id={run_summary['run_id']} status={run_summary['status']} "
            f"classification={packet1['classification']['truth_classification']} "
            f"profile={packet1['provenance']['actual_profile']}"
        )
        assert run_summary["status"] == "done"
        assert packet1["provenance"]["actual_model"] == alias_model
        assert packet1["provenance"]["actual_profile"] == "ollama.qwen.chatml.v1"
        assert packet1["provenance"]["primary_output_id"] == "agent_output/main.py"
        assert packet1["provenance"]["fallback_occurred"] is True
        assert packet1["provenance"]["execution_profile"] == "fallback"
        assert packet1["classification"]["truth_classification"] == "degraded"
        assert "silent_degraded_success" in packet1["defects"]["defect_families"]
        assert packet1["packet1_conformance"]["status"] == "non_conformant"
    finally:
        await _remove_ollama_alias(alias_model)


@pytest.mark.asyncio
async def test_packet1_live_corrective_reprompt_marks_repaired_truth(tmp_path: Path, monkeypatch) -> None:
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live packet1 proof.")

    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")

    original_complete = LocalModelProvider.complete
    corrupted_guard_turn = {"value": False}

    async def _corrupt_first_response(self, messages, runtime_context=None):
        response = await original_complete(self, messages, runtime_context=runtime_context)
        context = dict(runtime_context or {})
        role_tokens = {
            str(value).strip().lower()
            for value in (context.get("roles") or [context.get("role")])
            if str(value).strip()
        }
        if "integrity_guard" not in role_tokens or corrupted_guard_turn["value"]:
            return response
        corrupted_guard_turn["value"] = True
        raw = dict(getattr(response, "raw", {}) or {})
        return ModelResponse(content=f"Done.\n{response.content}", raw=raw)

    monkeypatch.setattr(LocalModelProvider, "complete", _corrupt_first_response)

    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "packet1_repaired_live.db")
    _write_core_assets(root, epic_id="packet1_repaired_live", environment_model=_live_model())

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("packet1_repaired_live")

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1
    run_summary = _read_json(run_roots[0] / "run_summary.json")
    packet1 = run_summary["truthful_runtime_packet1"]
    packet2 = run_summary["truthful_runtime_packet2"]
    event_rows = _read_jsonl(workspace / "orket.log")

    print(
        "[live][packet1][corrective-reprompt] "
        f"run_id={run_summary['run_id']} status={run_summary['status']} "
        f"classification={packet1['classification']['truth_classification']}"
    )
    assert any(
        str(row.get("event") or "") == "turn_corrective_reprompt"
        and str(((row.get("data") or {}).get("session_id") or "")) == run_summary["run_id"]
        for row in event_rows
    )
    assert run_summary["status"] == "done"
    assert packet1["provenance"]["primary_output_id"] == "agent_output/main.py"
    assert packet1["provenance"]["intended_model"] != PACKET1_MISSING_TOKEN
    assert packet1["provenance"]["intended_profile"] != PACKET1_MISSING_TOKEN
    assert packet1["provenance"]["repair_occurred"] is True
    assert packet1["classification"]["truth_classification"] == "repaired"
    assert packet1["defects"]["defect_families"] == ["silent_repaired_success"]
    assert packet1["packet1_conformance"]["status"] == "non_conformant"
    assert packet2["repair_ledger"]["repair_occurred"] is True
    assert packet2["repair_ledger"]["repair_count"] >= 1
    assert packet2["repair_ledger"]["final_disposition"] == "accepted_with_repair"
    assert any(
        entry["strategy"] == "corrective_reprompt"
        and entry["source_event"] == "turn_corrective_reprompt"
        and entry["material_change"] is True
        for entry in packet2["repair_ledger"]["entries"]
    )
