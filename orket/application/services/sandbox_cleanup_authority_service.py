from __future__ import annotations

from dataclasses import dataclass, field

from orket.core.domain.sandbox_cleanup import ObservedDockerResource
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class CleanupAuthorityDecision:
    compose_cleanup_allowed: bool
    fallback_resource_names: list[str]
    blocked_resource_names: list[str]
    reason_codes: list[str] = field(default_factory=list)


class SandboxCleanupAuthorityService:
    """Determines whether sandbox cleanup is authorized for observed resources."""

    def decide(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_resources: list[ObservedDockerResource],
        compose_path_available: bool,
        break_glass_approved: bool = False,
        approved_resource_names: set[str] | None = None,
    ) -> CleanupAuthorityDecision:
        approved_scope = approved_resource_names or set()
        fallback_allowed: list[str] = []
        blocked: list[str] = []
        reasons: list[str] = []
        host_context_match = True
        positive_authority_present = False

        for resource in observed_resources:
            matches_host = (
                resource.docker_context == record.docker_context
                and self._host_context_matches(
                    record_host_id=record.docker_host_id,
                    observed_host_id=resource.docker_host_id,
                )
            )
            if not matches_host:
                host_context_match = False
                blocked.append(resource.name)
                continue
            if self._has_positive_labels(record=record, resource=resource):
                positive_authority_present = True
                fallback_allowed.append(resource.name)
                continue
            if break_glass_approved and resource.name in approved_scope:
                fallback_allowed.append(resource.name)
                reasons.append("break_glass_scope_applied")
                continue
            blocked.append(resource.name)

        if not host_context_match:
            reasons.append("host_context_mismatch")
        if blocked and not break_glass_approved:
            reasons.append("missing_positive_authority")

        compose_cleanup_allowed = (
            compose_path_available
            and host_context_match
            and record.compose_project.startswith("orket-sandbox-")
            and (positive_authority_present or bool(record.compose_project))
        )
        if compose_cleanup_allowed:
            reasons.append("compose_project_authority")
        if not compose_cleanup_allowed and compose_path_available:
            reasons.append("compose_cleanup_blocked")

        return CleanupAuthorityDecision(
            compose_cleanup_allowed=compose_cleanup_allowed,
            fallback_resource_names=sorted(set(fallback_allowed)),
            blocked_resource_names=sorted(set(blocked)),
            reason_codes=sorted(set(reasons)),
        )

    @staticmethod
    def _has_positive_labels(*, record: SandboxLifecycleRecord, resource: ObservedDockerResource) -> bool:
        labels = {str(key): str(value) for key, value in (resource.labels or {}).items()}
        if labels.get("orket.managed") != "true":
            return False
        if labels.get("orket.sandbox_id") != record.sandbox_id:
            return False
        run_id = str(record.run_id or "").strip()
        if run_id and labels.get("orket.run_id") != run_id:
            return False
        return True

    @classmethod
    def _host_context_matches(cls, *, record_host_id: str, observed_host_id: str) -> bool:
        return cls._stable_host_token(record_host_id) == cls._stable_host_token(observed_host_id)

    @staticmethod
    def _stable_host_token(host_id: str) -> str:
        token = str(host_id or "").strip()
        head, separator, tail = token.partition(":")
        if separator and tail.isdigit():
            return head
        return token
