"""Integration: native preparation and executable acceptance, without model inference."""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_service import CardAcceptanceService
from orket.core.contracts.card_acceptance_inputs import PythonCliAcceptance
from scripts.governance.check_workflow_preflight import inspect_workflow

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def prepare(project, workflow):
    result = subprocess.run([sys.executable, str(ROOT / "examples/stored_workflows/prepare.py"),
                             str(project), "--workflow", workflow],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return project / "workspace"


def test_prepared_collection_seeds_each_member_without_touching_operator_board(tmp_path):
    board = ROOT / "model/core/rocks/run_the_business.json"
    before = board.read_bytes()
    project = tmp_path / "collection"
    workspace = prepare(project, "test_rock")
    members = json.loads((project / "model/core/rocks/test_rock.json").read_text())["epics"]
    assert {member["epic"] for member in members} == {"qa_completion_test", "sanity_test"}
    assert all(inspect_workflow(project, member["epic"])["ready"] for member in members)
    assert (workspace / "sanity_test/agent_output/organization.json").is_file()
    assert not (workspace / "agent_output").exists()
    result = subprocess.run([sys.executable, str(workspace / "qa_completion_test/agent_output/main.py"), "-2", "9"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and json.loads(result.stdout) == 7
    assert board.read_bytes() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("incorrect", [False, True])
async def test_factorial_recipe_matches_bank_and_native_acceptance_rejects_wrong_answers(tmp_path, incorrect):
    project = tmp_path / "factorial"
    workspace = await asyncio.to_thread(prepare, project, "factorial")
    def inputs():
        epic = json.loads((project / "model/core/epics/factorial.json").read_text())
        assert epic == json.loads((ROOT / "model/core/epics/factorial.json").read_text())
        assert epic["issues"][0]["params"]["runtime_verifier"]["commands"][0][0] == "python"
        bank = json.loads((ROOT / "benchmarks/task_bank/v2_realworld/tasks.json").read_text())
        assert json.loads((workspace / "task_context.json").read_text()) == next(t for t in bank if t["id"] == "008")
        source = "def factorial(n):\n    result = 1\n    for i in range(1, n+1):\n        result *= i\n    return result\n"
        (workspace / "agent_output/main.py").write_text("def factorial(n):\n    return 1\n" if incorrect else source)
        return PythonCliAcceptance.model_validate(epic["issues"][0]["params"]["completion_acceptance"])
    definition = await asyncio.to_thread(inputs)
    store = CardAcceptanceEvidenceStore(tmp_path / "evidence.sqlite3")
    result = await CardAcceptanceService(store).verify(
        workspace_root=workspace, definition=definition, card_id="LB-008-1", run_id="prepared-factorial",
        attempt_id="native-control", workload_inputs_json="{}")
    assert result.decision.sufficient is not incorrect
    assert json.loads(await store.read(result.evidence_digest))["commands"]
