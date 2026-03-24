# Layer: integration

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.adapters.storage.command_runner import CommandResult
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService
from orket.application.services.sandbox_runtime_recovery_service import SandboxRuntimeRecoveryService
from orket.core.domain import ClosureBasisClassification, LeaseStatus, ResultClass
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord
from orket.domain.verification import AGENT_OUTPUT_DIR


class FakeRecoveryRunner:
    def __init__(
        self,
        *,
        compose_project: str,
        sandbox_id: str,
        run_id: str,
        resources_present: bool = True,
        container_state: str = "running",
        inspect_payloads: list[list[dict[str, object]]] | None = None,
    ):
        self.compose_project = compose_project
        self.sandbox_id = sandbox_id
        self.run_id = run_id
        self.resources_present = resources_present
        self.container_state = container_state
        self.inspect_payloads = list(inspect_payloads or [])
        self.async_calls: list[tuple[str, ...]] = []

    async def run_async(self, *cmd: str) -> CommandResult:
        self.async_calls.append(cmd)
        if cmd[:2] == ("docker-compose", "-f") and "down" in cmd:
            self.resources_present = False
            return CommandResult(returncode=0, stdout="", stderr="")
        if cmd[:2] == ("docker", "inspect"):
            payload = self.inspect_payloads.pop(0) if self.inspect_payloads else self._inspect_payload()
            return CommandResult(returncode=0, stdout=json.dumps(payload), stderr="")
        if cmd[:3] == ("docker", "rm", "-f") or cmd[:3] == ("docker", "network", "rm") or cmd[:3] == ("docker", "volume", "rm"):
            self.resources_present = False
            return CommandResult(returncode=0, stdout="", stderr="")
        if cmd[:3] == ("docker", "ps", "-a"):
            return CommandResult(returncode=0, stdout=self._container_rows(), stderr="")
        if cmd[:3] == ("docker", "network", "ls"):
            return CommandResult(returncode=0, stdout=self._network_rows(), stderr="")
        if cmd[:3] == ("docker", "volume", "ls"):
            return CommandResult(returncode=0, stdout=self._volume_rows(), stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    def _container_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Names":"%s-api-1","State":"%s","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s,com.docker.compose.service=api"}\n'
            % (self.compose_project, self.container_state, self.sandbox_id, self.run_id)
        )

    def _network_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Name":"%s_default","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )

    def _volume_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Name":"%s_db-data","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )

    def _inspect_payload(self) -> list[dict[str, object]]:
        payload = {
            "Name": f"/{self.compose_project}-api-1",
            "RestartCount": 0,
            "Config": {"Labels": {"com.docker.compose.service": "api"}},
            "State": {"Status": self.container_state},
        }
        if self.container_state == "running":
            payload["State"]["Health"] = {"Status": "healthy"}
        return [payload]


class FakeOrphanDiscoveryRunner:
    def __init__(self) -> None:
        self.projects = [
            {"Name": "orket-sandbox-orphan-verified"},
            {"Name": "orket-sandbox-orphan-unverified"},
        ]

    async def run_async(self, *cmd: str) -> CommandResult:
        project = next(
            (
                token.split("=", 2)[-1]
                for token in cmd
                if token.startswith("label=com.docker.compose.project=")
            ),
            "",
        )
        if cmd[:3] == ("docker-compose", "ls", "--format"):
            return CommandResult(returncode=0, stdout=json.dumps(self.projects), stderr="")
        if cmd[:3] == ("docker", "ps", "-a"):
            return CommandResult(
                returncode=0,
                stdout=self._container_rows(project),
                stderr="",
            )
        if cmd[:3] == ("docker", "network", "ls"):
            return CommandResult(
                returncode=0,
                stdout=self._network_rows(project),
                stderr="",
            )
        if cmd[:3] == ("docker", "volume", "ls"):
            return CommandResult(
                returncode=0,
                stdout=self._volume_rows(project),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    @staticmethod
    def _container_rows(project: str) -> str:
        if project == "orket-sandbox-orphan-verified":
            return '{"Names":"verified-api-1","Labels":"orket.managed=true,orket.sandbox_id=orphan-verified,orket.run_id=run-verified"}\n'
        if project == "orket-sandbox-orphan-unverified":
            return '{"Names":"unverified-api-1","Labels":""}\n'
        return ""

    @staticmethod
    def _network_rows(project: str) -> str:
        if project == "orket-sandbox-orphan-verified":
            return '{"Name":"verified_default","Labels":"orket.managed=true,orket.sandbox_id=orphan-verified,orket.run_id=run-verified"}\n'
        if project == "orket-sandbox-orphan-unverified":
            return '{"Name":"unverified_default","Labels":""}\n'
        return ""

    @staticmethod
    def _volume_rows(project: str) -> str:
        if project == "orket-sandbox-orphan-verified":
            return '{"Name":"verified-data","Labels":"orket.managed=true,orket.sandbox_id=orphan-verified,orket.run_id=run-verified"}\n'
        if project == "orket-sandbox-orphan-unverified":
            return '{"Name":"unverified-data","Labels":""}\n'
        return ""


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "owner_instance_id": "runner-a",
        "lease_epoch": 1,
        "lease_expires_at": "2026-03-11T00:05:00+00:00",
        "state": SandboxState.STARTING,
        "cleanup_state": CleanupState.NONE,
        "record_version": 2,
        "created_at": "2026-03-11T00:00:00+00:00",
        "last_heartbeat_at": "2026-03-11T00:00:00+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": True,
        "cleanup_failure_reason": "sandbox-create-outcome-unknown",
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


def _service(tmp_path: Path, runner: FakeRecoveryRunner) -> tuple[AsyncSandboxLifecycleRepository, SandboxRuntimeRecoveryService]:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    lifecycle = SandboxRuntimeLifecycleService(
        repository=repo,
        command_runner=runner,
        instance_id="runner-a",
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )
    return repo, SandboxRuntimeRecoveryService(lifecycle_service=lifecycle)


@pytest.mark.asyncio
async def test_recovery_reconciles_blocked_starting_record_to_active_when_resources_exist(tmp_path) -> None:
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-sb-1", sandbox_id="sb-1", run_id="run-1")
    repo, recovery = _service(tmp_path, runner)
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    recovery.lifecycle_service.control_plane_publication = ControlPlanePublicationService(repository=control_plane_repo)
    recovery.lifecycle_service._now = staticmethod(lambda: "2026-03-11T00:01:00+00:00")
    await repo.save_record(_record())

    record = await recovery.reconcile_sandbox(sandbox_id="sb-1")
    lease = await control_plane_repo.get_latest_lease_record(lease_id="sandbox-lease:sb-1")

    assert record.state is SandboxState.ACTIVE
    assert record.requires_reconciliation is False
    assert record.managed_resource_inventory.containers == ["orket-sandbox-sb-1-api-1"]
    assert lease is not None
    assert lease.status is LeaseStatus.ACTIVE


@pytest.mark.asyncio
async def test_recovery_reconciles_blocked_starting_record_to_terminal_when_resources_are_absent(tmp_path) -> None:
    runner = FakeRecoveryRunner(
        compose_project="orket-sandbox-sb-1",
        sandbox_id="sb-1",
        run_id="run-1",
        resources_present=False,
    )
    repo, recovery = _service(tmp_path, runner)
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    recovery.lifecycle_service.control_plane_publication = ControlPlanePublicationService(repository=control_plane_repo)
    recovery.lifecycle_service._now = staticmethod(lambda: "2026-03-11T00:01:00+00:00")
    await repo.save_record(_record())

    record = await recovery.reconcile_sandbox(sandbox_id="sb-1")
    final_truth = await control_plane_repo.get_final_truth(run_id="run-1")

    assert record.state is SandboxState.TERMINAL
    assert record.cleanup_state is CleanupState.SCHEDULED
    assert record.terminal_reason is TerminalReason.START_FAILED
    assert record.requires_reconciliation is False
    assert record.required_evidence_ref is not None
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.FAILED
    assert final_truth.closure_basis is ClosureBasisClassification.NORMAL_EXECUTION


@pytest.mark.asyncio
async def test_recovery_reconciles_blocked_starting_record_to_terminal_when_runtime_is_not_running(tmp_path) -> None:
    runner = FakeRecoveryRunner(
        compose_project="orket-sandbox-sb-1",
        sandbox_id="sb-1",
        run_id="run-1",
        container_state="restarting",
    )
    repo, recovery = _service(tmp_path, runner)
    recovery.lifecycle_service._now = staticmethod(lambda: "2026-03-11T00:01:00+00:00")
    await repo.save_record(_record())

    record = await recovery.reconcile_sandbox(sandbox_id="sb-1")

    assert record.state is SandboxState.TERMINAL
    assert record.cleanup_state is CleanupState.SCHEDULED
    assert record.terminal_reason is TerminalReason.START_FAILED
    assert record.requires_reconciliation is False


@pytest.mark.asyncio
async def test_sweeper_executes_due_cleanup_for_terminal_record(tmp_path) -> None:
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-sb-1", sandbox_id="sb-1", run_id="run-1")
    repo, recovery = _service(tmp_path, runner)
    compose_path = tmp_path / AGENT_OUTPUT_DIR / "deployment"
    compose_path.mkdir(parents=True, exist_ok=True)
    (compose_path / "docker-compose.sandbox.yml").touch()
    await repo.save_record(
        _record(
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.SCHEDULED,
            record_version=4,
            requires_reconciliation=False,
            terminal_reason=TerminalReason.SUCCESS,
            terminal_at="2026-03-11T00:00:00+00:00",
            cleanup_due_at="2026-03-11T00:01:00+00:00",
            workspace_path=str(tmp_path),
        )
    )

    cleaned = await recovery.sweep_due_cleanups(max_records=1)
    stored = await repo.get_record("sb-1")
    events = await repo.list_events("sb-1")

    assert len(cleaned) == 1
    assert stored is not None
    assert stored.state is SandboxState.CLEANED
    assert stored.cleanup_state is CleanupState.COMPLETED
    assert stored.cleanup_attempts == 1
    assert any(event.event_type == "sandbox.cleanup_decision_evaluated" for event in events)
    assert any(event.event_type == "sandbox.cleanup_execution_result" for event in events)


@pytest.mark.asyncio
async def test_preview_due_cleanup_emits_dry_run_decision_with_reason_code(tmp_path) -> None:
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-sb-1", sandbox_id="sb-1", run_id="run-1")
    repo, recovery = _service(tmp_path, runner)
    compose_path = tmp_path / AGENT_OUTPUT_DIR / "deployment"
    compose_path.mkdir(parents=True, exist_ok=True)
    (compose_path / "docker-compose.sandbox.yml").touch()
    await repo.save_record(
        _record(
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.SCHEDULED,
            record_version=4,
            requires_reconciliation=False,
            terminal_reason=TerminalReason.SUCCESS,
            terminal_at="2026-03-11T00:00:00+00:00",
            cleanup_due_at="2026-03-11T00:01:00+00:00",
            workspace_path=str(tmp_path),
        )
    )

    previews = await recovery.preview_due_cleanups(max_records=1)
    events = await repo.list_events("sb-1")

    assert len(previews) == 1
    assert previews[0]["reason_code"] == "success"
    assert previews[0]["policy_match"] == "terminal_cleanup_due"
    assert previews[0]["dry_run"] is True
    assert previews[0]["cleanup_result"] == "would_execute_compose"
    assert any(
        event.event_type == "sandbox.cleanup_decision_evaluated" and event.payload["dry_run"] is True
        for event in events
    )


@pytest.mark.asyncio
async def test_orphan_discovery_persists_verified_and_unverified_orphan_records(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    lifecycle = SandboxRuntimeLifecycleService(
        repository=repo,
        command_runner=FakeOrphanDiscoveryRunner(),
        instance_id="runner-a",
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )
    recovery = SandboxRuntimeRecoveryService(lifecycle_service=lifecycle)

    created = await recovery.discover_orphans()
    records = {record.compose_project: record for record in created}

    assert set(records) == {"orket-sandbox-orphan-verified", "orket-sandbox-orphan-unverified"}
    assert records["orket-sandbox-orphan-verified"].terminal_reason is TerminalReason.ORPHAN_DETECTED
    verified_created = datetime.fromisoformat(records["orket-sandbox-orphan-verified"].created_at)
    verified_due = datetime.fromisoformat(str(records["orket-sandbox-orphan-verified"].cleanup_due_at))
    assert int((verified_due - verified_created).total_seconds()) == 3600
    assert records["orket-sandbox-orphan-verified"].cleanup_state is CleanupState.SCHEDULED
    assert records["orket-sandbox-orphan-unverified"].terminal_reason is TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP
    assert records["orket-sandbox-orphan-unverified"].cleanup_due_at is None


@pytest.mark.asyncio
async def test_sweeper_cleans_verified_orphan_without_compose_path_via_fallback_cleanup(tmp_path) -> None:
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-orphan-verified", sandbox_id="orphan-verified", run_id="run-verified")
    repo, recovery = _service(tmp_path, runner)
    await repo.save_record(
        SandboxLifecycleRecord(
            sandbox_id="orphan-verified",
            compose_project="orket-sandbox-orphan-verified",
            workspace_path="orphan:orket-sandbox-orphan-verified",
            run_id="run-verified",
            lease_epoch=0,
            state=SandboxState.ORPHANED,
            cleanup_state=CleanupState.SCHEDULED,
            record_version=1,
            created_at="2026-03-11T00:00:00+00:00",
            terminal_at="2026-03-11T00:00:00+00:00",
            terminal_reason=TerminalReason.ORPHAN_DETECTED,
            cleanup_due_at="2026-03-11T00:00:00+00:00",
            cleanup_attempts=0,
            managed_resource_inventory=ManagedResourceInventory(
                containers=["orket-sandbox-orphan-verified-api-1"],
                networks=["orket-sandbox-orphan-verified_default"],
                managed_volumes=["orket-sandbox-orphan-verified_db-data"],
            ),
            requires_reconciliation=False,
            docker_context="desktop-linux",
            docker_host_id="host-a",
        )
    )

    cleaned = await recovery.sweep_due_cleanups(max_records=1)
    stored = await repo.get_record("orphan-verified")

    assert len(cleaned) == 1
    assert stored is not None
    assert stored.state is SandboxState.CLEANED
    assert any(call[:3] == ("docker", "rm", "-f") for call in runner.async_calls)


@pytest.mark.asyncio
async def test_reclaimable_record_due_for_reclaim_ttl_transitions_to_terminal_cleanup(tmp_path, monkeypatch) -> None:
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-sb-1", sandbox_id="sb-1", run_id="run-1")
    repo, recovery = _service(tmp_path, runner)
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    recovery.lifecycle_service.control_plane_publication = ControlPlanePublicationService(repository=control_plane_repo)
    monkeypatch.setattr(recovery.lifecycle_service, "_now", staticmethod(lambda: "2026-03-11T03:00:00+00:00"))
    await repo.save_record(
        _record(
            state=SandboxState.RECLAIMABLE,
            cleanup_state=CleanupState.NONE,
            record_version=2,
            requires_reconciliation=False,
            terminal_reason=TerminalReason.LEASE_EXPIRED,
            cleanup_due_at="2026-03-11T02:00:00+00:00",
            terminal_at="2026-03-11T00:00:00+00:00",
        )
    )

    record = await recovery.reconcile_sandbox(sandbox_id="sb-1")
    final_truth = await control_plane_repo.get_final_truth(run_id="run-1")

    assert record.state is SandboxState.TERMINAL
    assert record.cleanup_state is CleanupState.SCHEDULED
    assert record.terminal_reason is TerminalReason.LEASE_EXPIRED
    assert record.required_evidence_ref is not None
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.BLOCKED
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP


@pytest.mark.asyncio
async def test_recovery_terminalizes_active_record_when_hard_max_age_is_elapsed(tmp_path, monkeypatch) -> None:
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-sb-1", sandbox_id="sb-1", run_id="run-1")
    repo, recovery = _service(tmp_path, runner)
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    recovery.lifecycle_service.control_plane_publication = ControlPlanePublicationService(repository=control_plane_repo)
    monkeypatch.setattr(recovery.lifecycle_service, "_now", staticmethod(lambda: "2026-03-11T03:00:00+00:00"))
    await repo.save_record(
        _record(
            state=SandboxState.ACTIVE,
            cleanup_state=CleanupState.NONE,
            record_version=2,
            requires_reconciliation=False,
            created_at="2026-03-01T00:00:00+00:00",
        )
    )

    record = await recovery.reconcile_sandbox(sandbox_id="sb-1")
    final_truth = await control_plane_repo.get_final_truth(run_id="run-1")

    assert record.state is SandboxState.TERMINAL
    assert record.cleanup_state is CleanupState.SCHEDULED
    assert record.terminal_reason is TerminalReason.HARD_MAX_AGE
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.BLOCKED
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP


@pytest.mark.asyncio
async def test_recovery_terminalizes_active_restart_loop_without_manual_health_check(tmp_path, monkeypatch) -> None:
    runner = FakeRecoveryRunner(
        compose_project="orket-sandbox-sb-1",
        sandbox_id="sb-1",
        run_id="run-1",
        inspect_payloads=[
            [
                {
                    "Name": "/orket-sandbox-sb-1-api-1",
                    "RestartCount": 0,
                    "Config": {"Labels": {"com.docker.compose.service": "api"}},
                    "State": {"Status": "running", "Health": {"Status": "unhealthy"}},
                }
            ],
            [
                {
                    "Name": "/orket-sandbox-sb-1-api-1",
                    "RestartCount": 0,
                    "Config": {"Labels": {"com.docker.compose.service": "api"}},
                    "State": {"Status": "running", "Health": {"Status": "unhealthy"}},
                }
            ],
        ],
    )
    repo, recovery = _service(tmp_path, runner)
    policy = SandboxLifecyclePolicy(
        restart_threshold_count=5,
        restart_window_seconds=300,
        unhealthy_duration_seconds=1,
    )
    recovery.lifecycle_service.policy = policy
    recovery.restart_policy.policy = policy
    moments = iter(["2026-03-11T00:00:00+00:00", "2026-03-11T00:00:02+00:00"])
    monkeypatch.setattr(recovery.lifecycle_service, "_now", staticmethod(lambda: next(moments)))
    await repo.save_record(
        _record(
            state=SandboxState.ACTIVE,
            cleanup_state=CleanupState.NONE,
            record_version=2,
            requires_reconciliation=False,
        )
    )

    first = await recovery.reconcile_sandbox(sandbox_id="sb-1")
    second = await recovery.reconcile_sandbox(sandbox_id="sb-1")

    assert first.state is SandboxState.ACTIVE
    assert second.state is SandboxState.TERMINAL
    assert second.cleanup_state is CleanupState.SCHEDULED
    assert second.terminal_reason is TerminalReason.RESTART_LOOP


@pytest.mark.asyncio
async def test_recovery_terminalizes_active_non_running_core_service_on_first_reconcile(tmp_path, monkeypatch) -> None:
    runner = FakeRecoveryRunner(
        compose_project="orket-sandbox-sb-1",
        sandbox_id="sb-1",
        run_id="run-1",
        container_state="restarting",
        inspect_payloads=[
            [
                {
                    "Name": "/orket-sandbox-sb-1-api-1",
                    "RestartCount": 681,
                    "Config": {"Labels": {"com.docker.compose.service": "api"}},
                    "State": {"Status": "restarting"},
                }
            ]
        ],
    )
    repo, recovery = _service(tmp_path, runner)
    monkeypatch.setattr(recovery.lifecycle_service, "_now", staticmethod(lambda: "2026-03-11T00:00:00+00:00"))
    await repo.save_record(
        _record(
            state=SandboxState.ACTIVE,
            cleanup_state=CleanupState.NONE,
            record_version=2,
            requires_reconciliation=False,
        )
    )

    record = await recovery.reconcile_sandbox(sandbox_id="sb-1")

    assert record.state is SandboxState.TERMINAL
    assert record.cleanup_state is CleanupState.SCHEDULED
    assert record.terminal_reason is TerminalReason.RESTART_LOOP
