import asyncio
import json
import time
from pathlib import Path

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from tests.turn_prompt_utils import extract_turn_prompt_context


class ParallelDummyProvider(LocalModelProvider):
    def __init__(self):
        self.model = "dummy"
        self.timeout = 300
        self.turns = 0
        self.active_calls = 0
        self.max_parallel = 0

    async def complete(self, messages):
        self.active_calls += 1
        self.max_parallel = max(self.max_parallel, self.active_calls)
        self.turns += 1

        # Artificial delay to simulate LLM latency and allow parallelism to be visible.
        await asyncio.sleep(0.5)

        turn_context = extract_turn_prompt_context(messages)
        active_role = str(turn_context.get("role") or "").strip().lower()
        if active_role in {"integrity_guard", "verifier_seat"}:
            self.active_calls -= 1
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                raw={"model": "dummy", "total_tokens": 50},
            )

        self.active_calls -= 1
        return ModelResponse(
            content='```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
            raw={"model": "dummy", "total_tokens": 100},
        )


def _seed_parallel_test_workspace(root: Path, *, company_name: str, epic_filename: str, epic_payload: dict) -> tuple[Path, str]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir()
    (root / "model" / "core").mkdir(parents=True)
    for directory_name in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / directory_name).mkdir()

    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()

    db_path = str(root / "test_parallel.db")

    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": company_name,
                "vision": "V",
                "ethos": "E",
                "branding": {"design_dos": []},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 10},
                "process_rules": {"small_project_builder_variant": "architect"},
                "departments": ["core"],
            }
        )
    )
    (root / "user_settings.json").write_text(json.dumps({}))

    for dialect_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{dialect_name}.json").write_text(
            json.dumps(
                {
                    "model_family": dialect_name,
                    "dsl_format": "JSON",
                    "constraints": [],
                    "hallucination_guard": "N",
                }
            )
        )

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "R1",
                "summary": "lead_architect",
                "type": "utility",
                "description": "D",
                "tools": ["update_issue_status"],
            }
        )
    )
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(
        json.dumps(
            {
                "id": "R2",
                "summary": "integrity_guard",
                "type": "utility",
                "description": "V",
                "tools": ["update_issue_status"],
            }
        )
    )
    (root / "model" / "core" / "roles" / "code_reviewer.json").write_text(
        json.dumps(
            {
                "id": "R3",
                "summary": "code_reviewer",
                "type": "utility",
                "description": "R",
                "tools": ["update_issue_status"],
            }
        )
    )
    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps(
            {
                "name": "standard",
                "seats": {
                    "lead_architect": {"name": "L", "roles": ["lead_architect"]},
                    "reviewer_seat": {"name": "R", "roles": ["code_reviewer"]},
                    "verifier_seat": {"name": "V", "roles": ["integrity_guard"]},
                },
            }
        )
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1})
    )
    (root / "model" / "core" / "epics" / epic_filename).write_text(json.dumps(epic_payload))

    return workspace, db_path


async def _run_epic_with_dummy_provider(
    *,
    root: Path,
    epic_name: str,
    company_name: str,
    epic_filename: str,
    epic_payload: dict,
    monkeypatch,
):
    workspace, db_path = _seed_parallel_test_workspace(
        root,
        company_name=company_name,
        epic_filename=epic_filename,
        epic_payload=epic_payload,
    )

    dummy_provider = ParallelDummyProvider()
    monkeypatch.setattr(LocalModelProvider, "__init__", lambda *args, **kwargs: None)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)

    start_time = time.perf_counter()
    await engine.run_epic(epic_name)
    total_duration = time.perf_counter() - start_time
    return total_duration, dummy_provider, engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parallel_execution_throughput(tmp_path, monkeypatch):
    """
    Verifies that independent issues are executed in parallel.
    The assertion compares a parallel-ready epic against a serial dependency chain
    under the same local test conditions, which is more stable than a fixed
    machine-dependent wall-clock threshold.
    """
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "true")

    parallel_duration, parallel_provider, parallel_engine = await _run_epic_with_dummy_provider(
        root=tmp_path / "parallel",
        epic_name="parallel_epic",
        company_name="Parallel Corp",
        epic_filename="parallel_epic.json",
        epic_payload={
            "id": "EPIC-P",
            "name": "Parallel",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "architecture_governance": {"idesign": False},
            "issues": [
                {"id": "P1", "summary": "Task 1", "seat": "lead_architect", "depends_on": []},
                {"id": "P2", "summary": "Task 2", "seat": "lead_architect", "depends_on": []},
                {"id": "P3", "summary": "Task 3", "seat": "lead_architect", "depends_on": []},
            ],
        },
        monkeypatch=monkeypatch,
    )
    serial_duration, serial_provider, _serial_engine = await _run_epic_with_dummy_provider(
        root=tmp_path / "serial",
        epic_name="chain_epic",
        company_name="Serial Corp",
        epic_filename="chain_epic.json",
        epic_payload={
            "id": "EPIC-C",
            "name": "Chain",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "architecture_governance": {"idesign": False},
            "issues": [
                {"id": "C1", "summary": "Task 1", "seat": "lead_architect", "depends_on": []},
                {"id": "C2", "summary": "Task 2", "seat": "lead_architect", "depends_on": ["C1"]},
                {"id": "C3", "summary": "Task 3", "seat": "lead_architect", "depends_on": ["C2"]},
            ],
        },
        monkeypatch=monkeypatch,
    )

    print(f"Parallel Duration: {parallel_duration:.2f}s")
    print(f"Serial Duration: {serial_duration:.2f}s")
    print(f"Parallel Max Calls: {parallel_provider.max_parallel}")
    print(f"Serial Max Calls: {serial_provider.max_parallel}")

    assert parallel_provider.max_parallel > 1, "Should have executed at least some calls in parallel"
    assert serial_provider.max_parallel == 1, "Serial dependency chain should not run in parallel"
    assert parallel_duration < serial_duration * 0.85, (
        "Expected parallel execution to be materially faster than the serial dependency chain, "
        f"got parallel={parallel_duration:.2f}s serial={serial_duration:.2f}s"
    )

    p1 = await parallel_engine.cards.get_by_id("P1")
    p2 = await parallel_engine.cards.get_by_id("P2")
    p3 = await parallel_engine.cards.get_by_id("P3")

    assert p1.status == "done"
    assert p2.status == "done"
    assert p3.status == "done"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dependency_chain_serial(tmp_path, monkeypatch):
    """
    Verifies that dependent issues are still executed serially.
    P1 -> P2 -> P3
    """
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "true")

    _duration, dummy_provider, engine = await _run_epic_with_dummy_provider(
        root=tmp_path,
        epic_name="chain_epic",
        company_name="Serial Corp",
        epic_filename="chain_epic.json",
        epic_payload={
            "id": "EPIC-C",
            "name": "Chain",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "architecture_governance": {"idesign": False},
            "issues": [
                {"id": "C1", "summary": "Task 1", "seat": "lead_architect", "depends_on": []},
                {"id": "C2", "summary": "Task 2", "seat": "lead_architect", "depends_on": ["C1"]},
                {"id": "C3", "summary": "Task 3", "seat": "lead_architect", "depends_on": ["C2"]},
            ],
        },
        monkeypatch=monkeypatch,
    )

    assert dummy_provider.max_parallel == 1, "Chain should have been executed serially"

    c3 = await engine.cards.get_by_id("C3")
    assert c3.status == "done"
