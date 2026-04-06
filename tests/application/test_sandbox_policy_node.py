from types import SimpleNamespace

import pytest

from orket.core.domain.sandbox import PortAllocation
from orket.decision_nodes.builtins import DefaultSandboxPolicyNode


def test_default_sandbox_policy_rejects_unknown_database_url_stack():
    """Layer: unit. Verifies unsupported stacks fail before advertising a bogus default database URL."""
    node = DefaultSandboxPolicyNode()
    ports = PortAllocation(api=8001, frontend=3001, database=5433, admin_tool=8081)

    with pytest.raises(ValueError, match="Unsupported tech stack"):
        node.get_database_url(SimpleNamespace(value="unknown-stack"), ports, db_password="secret")
