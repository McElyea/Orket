"""Real handoff packages, retained SQLite authority, and bounded native file holds."""
from __future__ import annotations

import asyncio
import io
import threading
from functools import partial
from pathlib import Path

from orket.application.services import trust_handoff_admission as admission
from orket.core.domain import AttemptState, RunState
from scripts.proof.trust_handoff_emitter import emit_trust_handoff_package
from tests.helpers.evidence_ownership import settle_evidence
from tests.kernel.v1.test_trust_handoff_admission import _payload, _services

SOURCE = Path(__file__).parents[1] / "proof_fixtures/outward_run/base_approved_package"
RUN_ID = "held-handoff-target"


def emit_package(package, *, rejected=False):
    emit_trust_handoff_package(source_run_id="run-live-proof", target_agent_id=RUN_ID,
        scope_id="scope-packet1", out_dir=package, source_package=SOURCE)
    if rejected:
        (package / "artifacts/committed_output").write_bytes(b"tampered actual artifact")


async def prepare_handoff(root, *, rejected=False, package_ref=None):
    package = root / "selected/package"
    await asyncio.to_thread(emit_package, package, rejected=rejected)
    runs, execution, events = await _services(root)
    payload = _payload(RUN_ID, package if package_ref is None else package_ref)
    # This supported admission-only run has no later model/tool step.
    del payload["task"]["acceptance_contract"]["governed_tool_call"]
    submitted = await runs.submit(payload)
    return package, submitted, execution, events


async def retained_authority(execution):
    async with execution.approval_service.unit_of_work.transaction() as transaction:
        run = await transaction.get_run(RUN_ID)
        shared = await transaction.control_plane.execution.get_run_record(run_id=RUN_ID)
        attempt = await transaction.control_plane.execution.get_attempt_record(attempt_id=shared.current_attempt_id)
        truth = await transaction.control_plane.records.get_final_truth(run_id=RUN_ID)
    return run, shared, attempt, truth


async def assert_pending_authority(execution, events):
    run, shared, attempt, truth = await retained_authority(execution)
    assert run.status == "queued" and run.completed_at is None and truth is None
    assert shared.lifecycle_state is RunState.EXECUTING and attempt.attempt_state is AttemptState.EXECUTING
    assert attempt.end_timestamp is None
    assert [event.event_type for event in await events.list_for_run(RUN_ID)] == ["run_submitted"]


class PackageProbe:
    """Hold real metadata/read/close; finish means the entire verifier returned."""

    def __init__(self, monkeypatch, package, boundary, *, failure=None):
        self.package, self.boundary, self.failure = package, boundary, failure
        self.entered, self.release, self.finished = (threading.Event() for _ in range(3))
        self.thread, self.expired = None, False
        self.streams, self.reports = [], []
        self._observe_verifier(monkeypatch)
        self._observe_files(monkeypatch)

    def _pause(self, operation):
        if self.entered.is_set():
            return operation()
        self.thread = threading.get_ident()
        self.entered.set()
        self.expired = not self.release.wait(10)
        assert not self.expired, "native package operation was not released"
        result = operation()
        if self.failure is not None:
            raise self.failure
        return result

    def _observe_verifier(self, monkeypatch):
        original = admission.verify_trust_handoff_package

        def verify(*args, **kwargs):
            try:
                result = original(*args, **kwargs)
                self.reports.append(result)
                return result
            finally:
                self.finished.set()

        monkeypatch.setattr(admission, "verify_trust_handoff_package", verify)

    def _observe_files(self, monkeypatch):
        original_resolve, original_open = Path.resolve, io.open

        def resolve(path, *args, **kwargs):
            operation = partial(original_resolve, path, *args, **kwargs)
            return self._pause(operation) if self.boundary == "resolve" and path.name == self.package.name else operation()

        def native_open(file, *args, **kwargs):
            stream = original_open(file, *args, **kwargs)
            if isinstance(file, int) or not Path(file).is_relative_to(self.package):
                return stream
            self.streams.append(stream)
            selected = self.package / ("manifest.json" if self.boundary == "manifest" else "artifacts/committed_output")
            if Path(file) == selected and self.boundary != "resolve":
                operation = "close" if self.boundary == "close" else "read"
                original = getattr(stream, operation)
                setattr(stream, operation, lambda *values, **options: self._pause(partial(original, *values, **options)))
            return stream

        monkeypatch.setattr(Path, "resolve", resolve)
        monkeypatch.setattr(io, "open", native_open)

    def assert_closed(self):
        assert self.finished.is_set() and not self.expired
        assert self.streams and all(stream.closed for stream in self.streams), "verifier returned with an open package stream"

    async def cleanup(self, task):
        # Existing fixture cleanup waits finished, then explicitly closes only
        # abandoned handles. Product closure assertions run before this call.
        await settle_evidence(task, self)
