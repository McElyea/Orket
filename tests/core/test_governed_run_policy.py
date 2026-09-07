from __future__ import annotations

from orket.core.domain.governed_run_policy import GovernedRunPolicy, classify_action, decide_action


def test_governed_run_policy_classifies_and_decides_default_actions() -> None:
    """Layer: unit. Proves the governed-run demo policy defaults match the advertised risk model."""
    policy = GovernedRunPolicy()

    read_decision = decide_action({"kind": "list", "target": "."}, policy)
    write_decision = decide_action({"kind": "edit", "target": "config.yaml"}, policy)
    shell_decision = decide_action({"kind": "shell", "command": "rm -rf tmp/demo-cache"}, policy)
    network_decision = decide_action({"kind": "network", "target": "https://example.invalid"}, policy)
    unknown_decision = decide_action({"kind": "launch"}, policy)

    assert classify_action({"kind": "inspect"}).risk == "read_only"
    assert read_decision.decision == "allow"
    assert write_decision.decision == "requires_approval"
    assert write_decision.approval_required is True
    assert shell_decision.decision == "deny"
    assert network_decision.decision == "deny"
    assert unknown_decision.decision == "deny"


def test_governed_run_policy_allows_exact_allowlisted_shell_command() -> None:
    """Layer: unit. Proves shell allowlisting is exact and deny-by-default."""
    policy = GovernedRunPolicy(shell_allowlist=("echo governed",))

    allowed = decide_action({"kind": "shell", "command": "echo governed"}, policy)
    denied = decide_action({"kind": "shell", "command": "echo governed "}, policy)

    assert allowed.decision == "allow"
    assert denied.decision == "deny"
