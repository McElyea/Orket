from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxLifecycleError, SandboxState, TerminalReason


SANDBOX_LIFECYCLE_SCHEMA_VERSION = "1.0"
SANDBOX_LIFECYCLE_POLICY_VERSION = "docker_sandbox_lifecycle.v1"
SUPPORTED_SANDBOX_LIFECYCLE_SCHEMA_VERSIONS = frozenset({SANDBOX_LIFECYCLE_SCHEMA_VERSION})
SUPPORTED_SANDBOX_LIFECYCLE_POLICY_VERSIONS = frozenset({SANDBOX_LIFECYCLE_POLICY_VERSION})


class ManagedResourceInventory(BaseModel):
    containers: list[str] = Field(default_factory=list)
    networks: list[str] = Field(default_factory=list)
    managed_volumes: list[str] = Field(default_factory=list)


class SandboxLifecycleRecord(BaseModel):
    schema_version: str = SANDBOX_LIFECYCLE_SCHEMA_VERSION
    policy_version: str = SANDBOX_LIFECYCLE_POLICY_VERSION
    sandbox_id: str
    compose_project: str
    workspace_path: str
    run_id: str | None = None
    session_id: str | None = None
    owner_instance_id: str | None = None
    cleanup_owner_instance_id: str | None = None
    lease_epoch: int
    lease_expires_at: str | None = None
    state: SandboxState
    cleanup_state: CleanupState
    record_version: int
    created_at: str
    last_heartbeat_at: str | None = None
    terminal_at: str | None = None
    terminal_reason: TerminalReason | None = None
    cleanup_due_at: str | None = None
    cleanup_attempts: int
    cleanup_last_error: str | None = None
    cleanup_failure_reason: str | None = None
    required_evidence_ref: str | None = None
    managed_resource_inventory: ManagedResourceInventory
    requires_reconciliation: bool
    docker_context: str
    docker_host_id: str

    @model_validator(mode="after")
    def _validate_record(self) -> SandboxLifecycleRecord:
        ensure_supported_versions(self.schema_version, self.policy_version)
        if not (self.run_id or self.session_id):
            raise SandboxLifecycleError("Sandbox lifecycle record requires run_id or session_id.")
        if self.record_version < 1:
            raise SandboxLifecycleError("Sandbox lifecycle record_version must be >= 1.")
        if self.lease_epoch < 0:
            raise SandboxLifecycleError("Sandbox lifecycle lease_epoch must be >= 0.")
        if self.cleanup_attempts < 0:
            raise SandboxLifecycleError("Sandbox lifecycle cleanup_attempts must be >= 0.")
        if (
            self.state
            in {
                SandboxState.TERMINAL,
                SandboxState.RECLAIMABLE,
                SandboxState.ORPHANED,
                SandboxState.CLEANED,
            }
            and self.terminal_reason is None
        ):
            raise SandboxLifecycleError(
                "Sandbox lifecycle terminal_reason is required for terminal, reclaimable, orphaned, and cleaned states."
            )
        return self


class SandboxOperationDedupeEntry(BaseModel):
    operation_id: str
    payload_hash: str
    result_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SandboxApprovalRecord(BaseModel):
    approval_id: str
    sandbox_id: str
    action: str
    approved_by: str
    reason: str | None = None
    created_at: str
    revoked_by: str | None = None
    revoked_at: str | None = None


class SandboxLifecycleEventRecord(BaseModel):
    event_id: str
    sandbox_id: str | None = None
    event_kind: str
    event_type: str
    created_at: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SandboxLifecycleSnapshotRecord(BaseModel):
    snapshot_id: str
    sandbox_id: str
    record_version: int
    created_at: str
    integrity_digest: str
    record: SandboxLifecycleRecord


def ensure_supported_versions(schema_version: str, policy_version: str) -> bool:
    if schema_version not in SUPPORTED_SANDBOX_LIFECYCLE_SCHEMA_VERSIONS:
        raise SandboxLifecycleError(f"Unsupported sandbox lifecycle schema_version: {schema_version}.")
    interpret_policy_version(policy_version)
    return True


def interpret_policy_version(policy_version: str) -> str:
    if policy_version not in SUPPORTED_SANDBOX_LIFECYCLE_POLICY_VERSIONS:
        raise SandboxLifecycleError(f"Unsupported sandbox lifecycle policy_version: {policy_version}.")
    return policy_version
