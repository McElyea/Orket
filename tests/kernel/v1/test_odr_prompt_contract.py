from orket.kernel.v1.odr.prompt_contract import build_architect_messages, build_auditor_messages


def test_build_architect_messages_appends_extra_rules() -> None:
    """Layer: contract. Verifies loop-shape hardening can add extra architect rules without changing the canonical section contract."""
    messages = build_architect_messages(
        task="Refine retention requirements.",
        current_requirement="The system must store data locally.",
        prior_auditor_output="- none",
        extra_rules=["Resolve cited unresolved issues before introducing a new requirement theme."],
    )

    system = messages[0]["content"]
    assert "### REQUIREMENT" in system
    assert "Resolve cited unresolved issues before introducing a new requirement theme." in system


def test_build_auditor_messages_appends_extra_rules() -> None:
    """Layer: contract. Verifies loop-shape hardening can add extra auditor rules while preserving the canonical patch section contract."""
    messages = build_auditor_messages(
        task="Refine retention requirements.",
        architect_output="### REQUIREMENT\nThe system must store data locally.",
        extra_rules=["Each PATCHES bullet must cite an exact unresolved issue or architect phrase."],
    )

    system = messages[0]["content"]
    assert "### PATCHES" in system
    assert "Each PATCHES bullet must cite an exact unresolved issue or architect phrase." in system
