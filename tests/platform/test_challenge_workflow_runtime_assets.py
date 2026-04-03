from pathlib import Path

import pytest

from orket.orket import ConfigLoader
from orket.schema import EpicConfig, TeamConfig

pytestmark = pytest.mark.unit


def test_challenge_workflow_runtime_assets_load_from_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    loader = ConfigLoader(repo_root)

    team = loader.load_asset("teams", "challenge_coder_guard_team", TeamConfig)
    epic = loader.load_asset("epics", "challenge_workflow_runtime", EpicConfig)

    assert sorted(team.seats.keys()) == ["coder", "integrity_guard"]
    assert epic.team == "challenge_coder_guard_team"
    assert epic.params["cards_runtime"]["scenario_truth"]["expected_terminal_status"] == "done"
    assert len(epic.issues) == 12
    assert all(issue.seat == "coder" for issue in epic.issues)
    assert sum(
        1 for issue in epic.issues if issue.params.get("execution_profile") == "build_app_v1"
    ) == 1
    assert epic.issues[-1].id == "CWR-12"
