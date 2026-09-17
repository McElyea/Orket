"""Model structural proposals cannot publish their own completion authority."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from orket.adapters.tools.families.cards import CardManagementTools
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.driver import OrketDriver
from orket.schema import CardStatus
from tests.helpers.card_completion import completion_components, text_acceptance

pytestmark = pytest.mark.integration


def _driver(root):
    for category in ("epics", "rocks"):
        (root / "model/core" / category).mkdir(parents=True)
    (root / "model/core/epics/parent.json").write_text(json.dumps({"name": "parent", "issues": []}), encoding="utf-8")
    (root / "model/core/rocks/parent.json").write_text(json.dumps({"name": "parent", "epics": []}), encoding="utf-8")
    return OrketDriver(project_root=root, provider=SimpleNamespace(model="unused-model"))


def _asset_snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.json")}


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ["epic_params", "epic_issues", "epic_cards", "rock_children", "issue_params"])
# Layer: integration
async def test_model_structural_acceptance_is_rejected_before_any_asset_write(tmp_path, monkeypatch, shape):
    monkeypatch.chdir(tmp_path)
    driver = _driver(tmp_path)
    definition = text_acceptance("agent_output/proposed.txt", "trivial", workload_id="proposal").model_dump(mode="json")
    child = {"id": "PROPOSED-1", "summary": "Task", "seat": "coder", "params": {"completion_acceptance": definition}}
    asset = {"name": "proposed"}
    action = "create_epic"
    if shape == "epic_params":
        asset["params"] = child["params"]
    elif shape in {"epic_issues", "epic_cards"}:
        asset[shape.removeprefix("epic_")] = [child]
    elif shape == "rock_children":
        action, asset["epics"] = "create_rock", [{"issues": [child]}]
    else:
        action, asset = "create_issue", child
    before = _asset_snapshot(driver.model_root)
    result = await driver.execute_plan({"action": action, "new_asset": asset, "target_parent": "parent"})
    assert result.startswith("Error: E_CARD_ACCEPTANCE_MODEL_DEFINITION_FORBIDDEN")
    assert "Strategic Insight:" not in result
    assert _asset_snapshot(driver.model_root) == before


@pytest.mark.asyncio
# Layer: integration
async def test_model_created_epic_has_no_implicit_acceptance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    driver = _driver(tmp_path)
    asset = {"name": "proposed", "issues": [{"id": "PROPOSED-1", "summary": "Write output", "seat": "coder",
             "note": 'Proposed completion_acceptance: {"expected_text":"trivial"}'}]}
    result = await driver.execute_plan({"action": "create_epic", "new_asset": asset, "target_parent": "parent"})
    assert "Created Epic" in result
    stored = json.loads((driver.model_root / "core/epics/proposed.json").read_text(encoding="utf-8"))
    repo, service = completion_components(tmp_path / "cards.db", tmp_path / "workspace")
    await repo.save(stored["issues"][0])
    bound = await service.begin_attempt(repo, card_id="PROPOSED-1", run_id="run", attempt_id="attempt")
    evaluation = await service.evaluate_attempt(repo, bound)
    assert bound is None and evaluation.request is None
    assert evaluation.decision.state.value == "not_evaluated" and not evaluation.decision.sufficient
    with pytest.raises(CardCompletionRejected, match="E_CARD_COMPLETION_EVIDENCE_REQUIRED"):
        await repo.update_status("PROPOSED-1", CardStatus.DONE)
    assert (await repo.get_by_id("PROPOSED-1")).status != CardStatus.DONE


@pytest.mark.asyncio
@pytest.mark.parametrize("nested", [False, True])
# Layer: integration
async def test_card_creation_tool_explicitly_rejects_model_acceptance_without_storage(tmp_path, nested):
    db_path = tmp_path / "cards.db"
    tools = CardManagementTools(tmp_path, [], db_path=str(db_path))
    supplied = {"completion_acceptance": text_acceptance(
        "agent_output/proposed.txt", "trivial", workload_id="proposal").model_dump(mode="json")}
    arguments = {"summary": "Task", "seat": "coder", **({"params": supplied} if nested else supplied)}
    result = await tools.create_issue(arguments, {"session_id": "run"})
    assert result["ok"] is False and result["error_code"] == "E_CARD_ACCEPTANCE_MODEL_DEFINITION_FORBIDDEN"
    assert not db_path.exists()
