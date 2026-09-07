from __future__ import annotations

from collections.abc import Iterable

from orket_extension_sdk.manifest import ExtensionManifest, unsupported_agent_host_features

# These features are admitted only through the dedicated governed-agent path.
# The generic extension executor still refuses all agent discriminator markers.
SUPPORTED_GOVERNED_AGENT_HOST_FEATURES: frozenset[str] = frozenset(
    {"agent_stdio_ipc.v1", "governed_agent_loop.v1"}
)


def validate_governed_agent_host_features(
    manifest: ExtensionManifest,
    *,
    supported_features: Iterable[str] = SUPPORTED_GOVERNED_AGENT_HOST_FEATURES,
) -> None:
    """Fail before install/invocation when an agent needs unavailable host features."""
    for workload in manifest.workloads:
        unsupported = unsupported_agent_host_features(
            workload,
            supported_features=supported_features,
        )
        if unsupported:
            raise ValueError(
                "E_AGENT_HOST_FEATURE_UNSUPPORTED: "
                f"{workload.workload_id}: {', '.join(unsupported)}"
            )
