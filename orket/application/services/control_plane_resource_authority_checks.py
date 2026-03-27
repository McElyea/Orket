from __future__ import annotations

from collections.abc import Callable

from orket.core.contracts import LeaseRecord, ResourceRecord


def require_resource_snapshot_matches_lease(
    *,
    resource: ResourceRecord | None,
    lease: LeaseRecord,
    expected_resource_kind: str,
    expected_namespace_scope: str,
    error_context: str,
    error_factory: Callable[[str], Exception],
) -> None:
    if resource is None:
        raise error_factory(f"{error_context} missing resource authority: {lease.resource_id}")
    if str(resource.resource_id or "").strip() != str(lease.resource_id or "").strip():
        raise error_factory(f"{error_context} resource id drift: {lease.resource_id}")
    if str(resource.resource_kind or "").strip() != str(expected_resource_kind or "").strip():
        raise error_factory(
            f"{error_context} resource kind drift: {resource.resource_kind!r} != {expected_resource_kind!r}"
        )
    namespace_scope = str(resource.namespace_scope or "").strip()
    expected_scope = str(expected_namespace_scope or "").strip()
    if not namespace_scope or namespace_scope != expected_scope:
        raise error_factory(
            f"{error_context} resource namespace scope drift: {namespace_scope!r} != {expected_scope!r}"
        )
    observed_state = str(resource.current_observed_state or "").strip()
    expected_prefix = f"lease_status:{lease.status.value};"
    if not observed_state.startswith(expected_prefix):
        raise error_factory(
            f"{error_context} resource state drift: {observed_state!r} does not start with {expected_prefix!r}"
        )


__all__ = ["require_resource_snapshot_matches_lease"]
