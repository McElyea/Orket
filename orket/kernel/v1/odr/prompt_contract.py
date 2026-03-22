from __future__ import annotations


def _rules_block(base_rules: list[str], extra_rules: list[str] | None = None) -> str:
    rows = [*base_rules, *[str(item).strip() for item in list(extra_rules or []) if str(item).strip()]]
    return "".join(f"- {row}\n" for row in rows)


def build_architect_messages(
    *,
    task: str,
    current_requirement: str,
    prior_auditor_output: str,
    extra_rules: list[str] | None = None,
) -> list[dict[str, str]]:
    system = (
        "You are the Architect role in a requirements refinement loop.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### REQUIREMENT\n"
        "### CHANGELOG\n"
        "### ASSUMPTIONS\n"
        "### OPEN_QUESTIONS\n"
        "Rules:\n"
        + _rules_block(
            [
                "No code fences.",
                "No source code.",
                "REQUIREMENT must be plain English, concrete, and testable.",
                "Put all required behavior, bounds, and controls in REQUIREMENT.",
                "Do not move required behavior into ASSUMPTIONS or OPEN_QUESTIONS.",
                "If a required value is missing, keep it in REQUIREMENT as DECISION_REQUIRED(field): detail.",
                "OPEN_QUESTIONS may only contain optional follow-up questions. Use '- none' when empty.",
                "Keep CHANGELOG, ASSUMPTIONS, and OPEN_QUESTIONS as short bullet lists.",
            ],
            extra_rules,
        )
    )
    user = (
        f"Task to refine:\n{task}\n\n"
        f"Current requirement draft:\n{current_requirement or '(none)'}\n\n"
        f"Prior auditor output:\n{prior_auditor_output or '(none)'}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_auditor_messages(
    *,
    task: str,
    architect_output: str,
    extra_rules: list[str] | None = None,
) -> list[dict[str, str]]:
    system = (
        "You are the Auditor role in a requirements refinement loop.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### CRITIQUE\n"
        "### PATCHES\n"
        "### EDGE_CASES\n"
        "### TEST_GAPS\n"
        "Rules:\n"
        + _rules_block(
            [
                "No code fences.",
                "No source code.",
                "Be adversarial and specific.",
                "Reject demotion of required behavior into ASSUMPTIONS or OPEN_QUESTIONS.",
                "Reject unresolved mandatory alternatives and hallucinated constants.",
                "Each PATCHES bullet must start with one class tag: [ADD], [REMOVE], [REWRITE], or [DECISION_REQUIRED].",
                "When you can infer a reasonable default from the task context, resolve the field with [REWRITE].",
                "Use [DECISION_REQUIRED] only when no reasonable default exists in the task context.",
                "Do not re-escalate a field that already has a concrete value in REQUIREMENT.",
            ],
            extra_rules,
        )
    )
    user = f"Original task:\n{task}\n\nArchitect output to audit:\n{architect_output}\n"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
