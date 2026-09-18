"""Test-owned standalone coordinator apps; no production module-global coupling."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_runtime_service import CoordinatorRuntimeService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain.coordinator_card import Card
from orket.interfaces.coordinator_api import create_coordinator_app
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


class Inputs(RuntimeInputService):
    """Explicit ordered wall time and independently controlled elapsed time."""

    def __init__(self):
        self.elapsed = 1000.0
        self.tick = 0

    def monotonic_seconds(self):
        return self.elapsed

    def utc_now(self):
        self.tick += 1
        return datetime(2026, 9, 18, tzinfo=UTC) + timedelta(seconds=self.tick)


def app_for(root, *, inputs=None, store=None, environment=None):
    app = create_coordinator_app(
        project_root=root, environment={} if environment is None else environment,
        runtime_inputs=inputs or Inputs(), store=store,
    )
    app.state.coordinator.store.reset([Card(id="card", payload={}, state="OPEN", hedged_execution=False)])
    return app


def client_for(app, *, raise_errors=True):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=raise_errors), base_url="http://test")


@dataclass
class CoordinatorHarness:
    owner: CoordinatorRuntimeService
    client: TestClient


@contextmanager
def coordinator_harness(root, *, publication=None, expected_failure=False):
    app = create_coordinator_app(project_root=root, environment={}, publication=publication)
    owner = app.state.coordinator
    client = TestClient(app, raise_server_exceptions=False)
    client.__enter__()
    try:
        yield CoordinatorHarness(owner, client)
    finally:
        if expected_failure:
            with pytest.raises(RuntimeError, match="failed transition"):
                client.__exit__(None, None, None)
            assert not owner.closed
        else:
            client.__exit__(None, None, None)
            assert owner.closed


@pytest.fixture
def coordinator(tmp_path, request):
    publication = ControlPlanePublicationService(repository=InMemoryControlPlaneRecordRepository())
    with coordinator_harness(tmp_path, publication=publication, expected_failure=getattr(request, "param", False)) as harness:
        yield harness


@pytest.fixture
def coordinator_sqlite(tmp_path):
    with coordinator_harness(tmp_path) as harness:
        yield harness
