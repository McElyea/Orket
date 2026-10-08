"""Layer: integration. Execute frozen multifile CLI programs through real acceptance."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance
from scripts.benchmarks.task_acceptance import declare_task_acceptance

pytestmark = pytest.mark.integration


def _prepare(root):
    epic = {"issues": [{"summary": "Implement CLI", "note": "Implement this CLI"}]}
    task = {"id": "cli", "evaluation": {"type": "cli_examples", "entrypoint": "agent_output/main.py",
            "artifact_paths": ["agent_output/main.py", "agent_output/implementation.py"], "examples": [
                {"args": ["a b", ""], "expected_stdout": 'a b\n', "expected_stderr": "", "expected_exit_code": 0},
                {"args": [], "expected_stdout": "", "expected_stderr": "error: two arguments\n", "expected_exit_code": 2}]}}
    declare_task_acceptance(epic, task, root)
    (root / "agent_output/main.py").write_text(
        'import sys\nfrom implementation import combine\n'
        'if len(sys.argv) != 3:\n    print("error: two arguments", file=sys.stderr)\n    sys.exit(2)\n'
        'print(combine(*sys.argv[1:]))\n', encoding="utf-8")
    (root / "agent_output/implementation.py").write_text('def combine(a, b):\n    return a + b\n', encoding="utf-8")
    return task, epic["issues"][0]["params"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["none", "wrong-computation", "wrong-error", "literal-newline", "missing-module"])
async def test_cli_acceptance_retains_multifile_behavior_and_refuses_wrong_outputs(tmp_path, mutation):
    task, params = await asyncio.to_thread(_prepare, tmp_path)
    definition = PythonCliAcceptance.model_validate(params["completion_acceptance"])
    implementation = tmp_path / "agent_output/implementation.py"
    if mutation == "wrong-computation":
        await asyncio.to_thread(implementation.write_text, 'def combine(a, b):\n    return "wrong"\n')
    elif mutation == "wrong-error":
        main = tmp_path / "agent_output/main.py"
        source = await asyncio.to_thread(main.read_text)
        await asyncio.to_thread(main.write_text, source.replace("error: two arguments", "wrong error"))
    elif mutation == "missing-module":
        await asyncio.to_thread(implementation.unlink)
    elif mutation == "literal-newline":
        task["evaluation"]["examples"][0]["expected_stdout"] = "a b\\n"
        epic = {"issues": [{"summary": "Implement CLI", "note": "Implement CLI"}]}
        await asyncio.to_thread(declare_task_acceptance, epic, task, tmp_path)
        definition = PythonCliAcceptance.model_validate(epic["issues"][0]["params"]["completion_acceptance"])
    store = CardAcceptanceEvidenceStore(tmp_path / "acceptance.sqlite3")
    service = CardAcceptanceService(store)
    result = await service.verify(workspace_root=tmp_path, definition=definition,
                                  card_id="card", run_id="run", attempt_id="attempt", workload_inputs_json="{}")
    assert result.decision.sufficient is (mutation == "none")
    if mutation in {"none", "wrong-computation", "wrong-error"}:
        support = await RuntimeVerifier(tmp_path, issue_params=params).verify()
        assert support.ok is (mutation == "none")
        assert support.command_results[0]["policy_source"] == "issue_override"
        if mutation == "wrong-error":
            assert support.command_results[0]["stdout_json"]["cases"][0]["stdout"] == "a b\n"
            assert any("cases[1]" in error for error in support.errors)
    retained = json.loads(await store.read(result.evidence_digest))
    if mutation == "none":
        assert {row["path"] for row in retained["artifacts"]} == set(definition.artifact_paths)
        assert len(retained["commands"]) == 2
        assert await service.inspect(result.evidence_digest, definition=definition,
                                     scope=result.decision.scope) == result.decision


def test_cli_refuses_undeclared_artifacts_before_writing_verifier(tmp_path):
    task = {"id": "unsafe", "evaluation": {"type": "cli_examples", "entrypoint": "elsewhere.py",
                                             "examples": [{"args": []}]}}
    with pytest.raises(ValueError, match="explicit artifact_paths"):
        declare_task_acceptance({"issues": [{"note": "CLI"}]}, task, tmp_path)
    assert not (tmp_path / "agent_output").exists()
