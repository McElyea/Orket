from __future__ import annotations

import pytest

from orket.adapters.tools.registry import (
    CONNECTOR_RISK_LEVELS,
    DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
    BuiltInConnectorMetadata,
    BuiltInConnectorRegistry,
)


@pytest.mark.unit
def test_builtin_connector_registry_exposes_phase0_metadata_shape() -> None:
    """Layer: unit. Verifies Phase 0 connector registry is the metadata source for v1 built-ins."""
    expected_names = (
        "create_directory",
        "delete_file",
        "http_get",
        "http_post",
        "read_file",
        "run_command",
        "write_file",
    )

    assert DEFAULT_BUILTIN_CONNECTOR_REGISTRY.names() == expected_names

    for name in expected_names:
        metadata = DEFAULT_BUILTIN_CONNECTOR_REGISTRY.get(name)
        assert metadata is not None
        assert metadata.args_schema["type"] == "object"
        assert metadata.risk_level in CONNECTOR_RISK_LEVELS
        assert isinstance(metadata.pii_fields, tuple)
        assert metadata.timeout_seconds > 0


@pytest.mark.unit
def test_builtin_connector_registry_rejects_unknown_risk_level() -> None:
    """Layer: unit. Verifies connector risk labels cannot drift outside the stable vocabulary."""
    registry = BuiltInConnectorRegistry()

    with pytest.raises(ValueError, match="unsupported connector risk_level"):
        registry.register(
            BuiltInConnectorMetadata(
                name="bad_connector",
                description="Bad connector",
                args_schema={"type": "object"},
                risk_level="unknown",  # type: ignore[arg-type]
            )
        )


@pytest.mark.unit
def test_builtin_connector_registry_rejects_non_positive_timeout() -> None:
    """Layer: unit. Verifies connector timeout metadata remains enforceable."""
    registry = BuiltInConnectorRegistry()

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        registry.register(
            BuiltInConnectorMetadata(
                name="bad_timeout",
                description="Bad timeout",
                args_schema={"type": "object"},
                risk_level="read",
                timeout_seconds=0,
            )
        )
