"""Select immutable policy values and own the boundary to native file observations."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage.outbound_policy_reader import read_outbound_policy
from orket.application.services.kernel_invocation_inputs import (
    capture_kernel_environment,
    capture_kernel_invocation_root,
)
from orket.core.contracts.outbound_policy import (
    OutboundPolicyInputs,
    environment_policy_config,
    merge_outbound_policy_config,
)


def load_outbound_policy_config_file(path: Path | str) -> dict[str, Any]:
    require_sync_context(code="E_OUTBOUND_POLICY_REQUIRES_ASYNC_OWNER")
    selected = Path(capture_kernel_invocation_root(path).root)
    return read_outbound_policy(selected)


def load_outbound_policy_config(
    config: Mapping[str, Any] | None = None, *, environment: Mapping[str, str] | None = None
) -> dict[str, Any]:
    observed = capture_kernel_environment(environment)
    return merge_outbound_policy_config(environment_policy_config(observed.values), config)


def capture_outbound_policy_inputs(
    config: Mapping[str, Any] | None = None, *, environment: Mapping[str, str] | None = None
) -> OutboundPolicyInputs:
    return OutboundPolicyInputs.from_config(load_outbound_policy_config(config, environment=environment))


def capture_api_outbound_policy(project_root: Path, environment: Mapping[str, str]) -> OutboundPolicyInputs:
    observed = capture_kernel_environment(environment)
    raw = str(observed.values.get("ORKET_OUTBOUND_POLICY_CONFIG_PATH") or "").strip()
    config = load_outbound_policy_config_file(project_root / raw) if raw else None
    return capture_outbound_policy_inputs(config, environment=observed.values)
