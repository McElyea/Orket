"""Open BT-5.3 predicate: shared persistence must preserve admitted inputs."""
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
    ControlPlaneExecutionConflictError,
)
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_family_terminal_authority import agent_flow, card_flow, outward_flow, retained_results

pytestmark = [pytest.mark.asyncio, pytest.mark.integration, pytest.mark.usefixtures("elapsed_agent_clock")]


@pytest.mark.parametrize('family', ['outward', 'cards', 'governed_agent'])
@pytest.mark.parametrize('change', [False, True], ids=['identical', 'changed-namespace'])
# Layer: integration
async def test_admitted_family_run_authority_cannot_be_overwritten(
    family, change, tmp_path, test_root, workspace, db_path, boundary, monkeypatch,
):
    if family == 'outward':
        db, _ = await outward_flow(tmp_path, boundary)
    elif family == 'cards':
        db, _ = await card_flow(test_root, workspace, db_path, monkeypatch)
    else:
        db, _ = await agent_flow(tmp_path)
    rows = await retained_results(db)
    assert len(rows) == 1 and rows[0]['truth']['result_class'] == 'success'
    repository = AsyncControlPlaneExecutionRepository(db)
    original = await repository.get_run_record(run_id=rows[0]['run']['run_id'])
    incoming = original.model_copy(update={'namespace_scope': 'not-the-admitted-scope'}) if change else original
    if change:
        with pytest.raises(ControlPlaneExecutionConflictError):
            await repository.save_run_record(record=incoming)
    else:
        assert await repository.save_run_record(record=incoming) == original
    assert await repository.get_run_record(run_id=original.run_id) == original
