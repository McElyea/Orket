from __future__ import annotations

from dataclasses import dataclass, field

from orket.core.domain.sandbox_cleanup import DockerResourceType, ObservedDockerResource
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class CleanupVerificationResult:
    success: bool
    remaining_expected: list[str]
    unexpected_managed_present: list[str]
    absent_expected: list[str] = field(default_factory=list)
    observation_complete: bool = True
    unverified_expected: list[str] = field(default_factory=list)


class SandboxCleanupVerificationService:
    """Compares observed Docker state with managed inventory after cleanup."""

    def verify_absence(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_resources: list[ObservedDockerResource],
        observation_complete: bool = True,
    ) -> CleanupVerificationResult:
        expected = {
            DockerResourceType.CONTAINER: set(record.managed_resource_inventory.containers),
            DockerResourceType.NETWORK: set(record.managed_resource_inventory.networks),
            DockerResourceType.MANAGED_VOLUME: set(record.managed_resource_inventory.managed_volumes),
        }
        expected_names = sorted(name for names in expected.values() for name in names)
        if not observation_complete:
            return CleanupVerificationResult(
                success=False,
                remaining_expected=[],
                unexpected_managed_present=[],
                absent_expected=[],
                observation_complete=False,
                unverified_expected=expected_names,
            )
        observed_by_type = {
            DockerResourceType.CONTAINER: set(),
            DockerResourceType.NETWORK: set(),
            DockerResourceType.MANAGED_VOLUME: set(),
        }
        unexpected_managed_present: list[str] = []

        for resource in observed_resources:
            observed_by_type[resource.resource_type].add(resource.name)
            if (
                resource.labels.get("orket.managed") == "true"
                and resource.labels.get("orket.sandbox_id") == record.sandbox_id
                and resource.name not in expected[resource.resource_type]
            ):
                unexpected_managed_present.append(resource.name)

        remaining_expected = sorted(
            name for resource_type, names in expected.items() for name in (names & observed_by_type[resource_type])
        )
        absent_expected = sorted(
            name for resource_type, names in expected.items() for name in (names - observed_by_type[resource_type])
        )
        return CleanupVerificationResult(
            success=not remaining_expected and not unexpected_managed_present,
            remaining_expected=remaining_expected,
            unexpected_managed_present=sorted(set(unexpected_managed_present)),
            absent_expected=absent_expected,
            observation_complete=True,
        )
