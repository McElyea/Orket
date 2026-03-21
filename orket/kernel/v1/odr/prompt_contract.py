from __future__ import annotations


def build_architect_messages(*, task: str, current_requirement: str, prior_auditor_output: str) -> list[dict[str, str]]:
    system = (
        "You are the Architect role in a requirements refinement loop.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### REQUIREMENT\n"
        "### CHANGELOG\n"
        "### ASSUMPTIONS\n"
        "### OPEN_QUESTIONS\n"
        "Rules:\n"
        "- No code fences.\n"
        "- No source code.\n"
        "- REQUIREMENT must be plain English, concrete, and testable.\n"
        "- Put all required behavior, bounds, and controls in REQUIREMENT.\n"
        "- Do not move required behavior into ASSUMPTIONS or OPEN_QUESTIONS.\n"
        "- If a required value is missing, keep it in REQUIREMENT as DECISION_REQUIRED(field): detail.\n"
        "- OPEN_QUESTIONS may only contain optional follow-up questions. Use '- none' when empty.\n"
        "- Keep CHANGELOG, ASSUMPTIONS, and OPEN_QUESTIONS as short bullet lists.\n"
    )
    user = (
        f"Task to refine:\n{task}\n\n"
        f"Current requirement draft:\n{current_requirement or '(none)'}\n\n"
        f"Prior auditor output:\n{prior_auditor_output or '(none)'}\n"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_auditor_messages(*, task: str, architect_output: str) -> list[dict[str, str]]:
    system = (
        "You are the Auditor role in a requirements refinement loop.\n"
        "Return exactly these four sections, once each, in this exact order:\n"
        "### CRITIQUE\n"
        "### PATCHES\n"
        "### EDGE_CASES\n"
        "### TEST_GAPS\n"
        "Rules:\n"
        "- No code fences.\n"
        "- No source code.\n"
        "- Be adversarial and specific.\n"
        "- Reject demotion of required behavior into ASSUMPTIONS or OPEN_QUESTIONS.\n"
        "- Reject unresolved mandatory alternatives and hallucinated constants.\n"
        "- Each PATCHES bullet must start with one class tag: [ADD], [REMOVE], [REWRITE], or [DECISION_REQUIRED].\n"
        "- When you can infer a reasonable default from the task context, resolve the field with [REWRITE].\n"
        "- Use [DECISION_REQUIRED] only when no reasonable default exists in the task context.\n"
        "- Do not re-escalate a field that already has a concrete value in REQUIREMENT.\n"
    )
    user = f"Original task:\n{task}\n\nArchitect output to audit:\n{architect_output}\n"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
