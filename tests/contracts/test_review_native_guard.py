"""Layer: contract. Review entrypoints refuse before native policy/transport work."""

import pytest

from orket.application.review import run_service
from orket.application.review.models import SnapshotBounds

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


@pytest.mark.parametrize(
    "operation,arguments",
    [
        ("run_pr", {"remote": "fixture", "repo": "fixture", "pr": 1}),
        ("run_diff", {"base_ref": "HEAD", "head_ref": "HEAD"}),
        ("run_files", {"ref": "HEAD", "paths": ["fixture.py"]}),
    ],
)
async def test_native_review_guard_precedes_policy_loading(tmp_path, monkeypatch, operation, arguments):
    def unexpected(**_kwargs):
        pytest.fail("native policy work reached from a running event loop")

    monkeypatch.setattr(run_service, "resolve_review_policy", unexpected)
    service = run_service.ReviewRunService(workspace=tmp_path, control_plane_db_path=tmp_path / "review.sqlite3")
    with pytest.raises(RuntimeError, match="E_REVIEW_RUN_REQUIRES_ASYNC_OWNER"):
        getattr(service, operation)(repo_root=tmp_path, bounds=SnapshotBounds(), **arguments)
