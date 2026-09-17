"""Borrow unit-test repositories; this fixture makes no persistence or rollback claim."""
from contextlib import asynccontextmanager

from orket.application.services.turn_tool_control_plane_support import digest
from orket.core.contracts import AttemptRecord, ResolvedConfigurationSnapshot, RunRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransaction
from orket.core.contracts.turn_tool_dispatch import TURN_TOOL_DISPATCH_CONTRACT
from orket.core.domain import AttemptState, RunState


def unit_control_plane_transactions(engine):
    @asynccontextmanager
    async def borrowed():
        yield ControlPlaneTransaction(
            execution=engine.control_plane_execution_repository,
            records=engine.control_plane_repository,
            pending_gates=engine.pending_gates,
        )

    return borrowed


async def seed_unit_turn_execution(engine, *, namespace='issue:ISS-1'):
    """Explicit in-memory admission fixture; runtime admission is proved with SQLite elsewhere."""
    payload = {'dispatch_contract': TURN_TOOL_DISPATCH_CONTRACT}
    run = RunRecord(
        run_id='turn-tool-run:sess-1:ISS-1:coder:0001', workload_id='turn-tool-workload:coder',
        workload_version='turn_tool_dispatcher.v1', policy_snapshot_id='policy-snapshot-1',
        policy_digest='sha256:policy-1', configuration_snapshot_id='config-snapshot-1',
        configuration_digest=digest(payload), creation_timestamp='2026-03-03T11:59:00+00:00',
        admission_decision_receipt_ref='approval-reservation:apr-1', namespace_scope=namespace,
        lifecycle_state=RunState.EXECUTING, current_attempt_id='turn-tool-attempt:sess-1:ISS-1:coder:0001:0001',
    )
    await engine.control_plane_repository.save_resolved_configuration_snapshot(snapshot=ResolvedConfigurationSnapshot(
        snapshot_id=run.configuration_snapshot_id, snapshot_digest=run.configuration_digest,
        created_at=run.creation_timestamp, source_refs=[run.admission_decision_receipt_ref], configuration_payload=payload,
    ))
    await engine.control_plane_execution_repository.save_run_record(record=run)
    await engine.control_plane_execution_repository.save_attempt_record(record=AttemptRecord(
        attempt_id=run.current_attempt_id, run_id=run.run_id, attempt_ordinal=1, attempt_state=AttemptState.EXECUTING,
        starting_state_snapshot_ref='turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001', start_timestamp=run.creation_timestamp,
    ))
