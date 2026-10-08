"""Integration: stored nonempty workflows load through today's real config boundary."""
import json
from pathlib import Path

import pytest

from orket.core.domain.records import IssueRecord
from orket.exceptions import CardNotFound
from orket.runtime.config.config_loader import ConfigLoader
from orket.schema import EpicConfig, RoleConfig, TeamConfig
from scripts.governance.check_workflow_preflight import inspect_workflow

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = [path for path in sorted((ROOT / "model").glob("*/epics/*.json"))
             if any(json.loads(path.read_text(encoding="utf-8")).get(key)
                    for key in ("issues", "stories", "cards"))]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: f"{path.parent.parent.name}/{path.stem}")
def test_all_nonempty_stored_workflows_have_stable_cards_loadable_roles_and_current_tools(path):
    loader = ConfigLoader(ROOT, path.parent.parent.name)
    epic = loader.load_asset("epics", path.stem, EpicConfig)
    team = loader.load_asset("teams", epic.team, TeamConfig)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert all(card.get("id") for card in raw["issues"])
    for issue in epic.issues:
        assert IssueRecord(id=issue.id, summary=issue.name, seat=issue.seat).summary
        assert issue.seat in team.seats
    for seat in team.seats.values():
        for name in seat.roles:
            assert loader.load_asset("roles", name, RoleConfig).tools
    result = inspect_workflow(ROOT, path.stem, path.parent.parent.name)
    assert result["ready"] and not result["errors"]


def test_quarantined_assets_are_retained_but_unavailable_to_runtime_discovery():
    manifest = json.loads((ROOT / "docs/quarantine/workflows/manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        original = ROOT / entry["original_path"]
        assert not original.exists()
        assert (ROOT / entry["quarantined_path"]).is_file()
        assert entry["reason"] and entry["restore_requires"]
        with pytest.raises(CardNotFound):
            ConfigLoader(ROOT, original.parent.parent.name).load_asset(
                original.parent.name, original.stem, EpicConfig if original.parent.name == "epics" else dict)


def test_remaining_collection_members_are_active_and_ready():
    # run_the_business is the operator-owned mutable catchment, not a test suite.
    for path in sorted((ROOT / "model").glob("*/rocks/*.json")):
        if path.stem == "run_the_business":
            continue
        for member in json.loads(path.read_text(encoding="utf-8"))["epics"]:
            assert inspect_workflow(ROOT, member["epic"], member["department"])["ready"]
