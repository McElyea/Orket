"""Integration: prepared challenge checks execute through retained native evidence."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from examples.stored_workflows.prepare import prepare
from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.core.contracts.card_acceptance_inputs import ArtifactAcceptance, PythonCliAcceptance
from scripts.governance.check_workflow_preflight import inspect_workflow

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_prepared_challenge_declares_all_cards_and_seeds_only_the_verifier(tmp_path):
    project = tmp_path / "challenge"
    prepare(project, "challenge_workflow_runtime", "selected-model")
    assert inspect_workflow(project, "challenge_workflow_runtime")["ready"]
    assert json.loads((project / "setup.json").read_text())["runtime_environment"] == {"ORKET_CONTEXT_WINDOW": "1"}
    output = project / "workspace/agent_output"
    assert sorted(path.name for path in output.iterdir()) == ["challenge_acceptance_runner.py"]
    assert (output / "challenge_acceptance_runner.py").read_bytes() == (
        ROOT / "examples/stored_workflows/challenge_acceptance_runner.py").read_bytes()
    epic = json.loads((project / "model/core/epics/challenge_workflow_runtime.json").read_text())
    assert len(epic["issues"]) == 12
    for card in epic["issues"]:
        value = card["params"]["completion_acceptance"]
        family = ArtifactAcceptance if value["schema_version"] == "card_artifact_acceptance.v1" else PythonCliAcceptance
        family.model_validate(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("actual,accepted", [(42, True), (43, False)])
async def test_challenge_bridge_retains_real_commands_and_rejects_wrong_json(tmp_path, actual, accepted):
    output = tmp_path / "agent_output"
    await asyncio.to_thread(output.mkdir)
    await asyncio.to_thread(shutil.copyfile, ROOT / "examples/stored_workflows/challenge_acceptance_runner.py",
                            output / "challenge_acceptance_runner.py")
    await asyncio.to_thread((output / "main.py").write_text, f'import json\nprint(json.dumps({{"answer":{actual}}}))\n')
    contract = {"commands": [["python", "agent_output/main.py"]], "expect_json_stdout": True,
                "json_assertions": [{"path": "answer", "op": "eq", "value": 42}]}
    definition = PythonCliAcceptance(acceptance_ref="challenge-test.v1", policy_ref="challenge-test.v1",
        workload_id="test", entrypoint="agent_output/challenge_acceptance_runner.py",
        artifact_paths=("agent_output/challenge_acceptance_runner.py", "agent_output/main.py"),
        cases=({"criterion_id": "answer", "description": "Native exact JSON result",
                "arguments": (json.dumps(contract),), "expected_json": '{"ok":true,"commands":1}'},))
    store = CardAcceptanceEvidenceStore(tmp_path / "evidence.sqlite3")
    service = CardAcceptanceService(store)
    result = await service.verify(workspace_root=tmp_path, definition=definition, card_id="card",
        run_id="run", attempt_id="attempt", workload_inputs_json="{}")
    assert result.decision.sufficient is accepted
    package = json.loads(await store.read(result.evidence_digest))
    outer = json.loads(package["commands"][0]["result_json"])["command_results"][0]
    inner = json.loads(outer["stderr"])["challenge_verification"]
    assert inner["command_results"][0]["process_lifetime"]["cleanup_confirmed"]
    assert json.loads(inner["command_results"][0]["stdout"]) == {"answer": actual}
    assert bool(inner["errors"]) is not accepted
