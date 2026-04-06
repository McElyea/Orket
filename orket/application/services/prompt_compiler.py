from __future__ import annotations

from orket.schema import DialectConfig, SkillConfig


class PromptCompiler:
    """
    Service responsible for assembling the final system instruction string.
    Implements card system protocols and optional structural constraints.
    """

    @staticmethod
    def _protocol_lines(protocol_governed_enabled: bool) -> list[str]:
        if protocol_governed_enabled:
            return [
                "- DO NOT narrate your plan in prose. Return exactly one JSON object.",
                (
                    '- Required response envelope: {"content":"","tool_calls":'
                    '[{"tool":"<tool_name>","args":{"key":"value"}}]}'
                ),
                "- In tool mode, content MUST be an empty string.",
                "- Put every required tool call into tool_calls within that single JSON object.",
                "- Do not use markdown fences or multiple top-level JSON objects.",
            ]
        return [
            "- DO NOT narrate your plan in prose. Emit executable JSON only.",
            '- For a single tool call, emit one compact JSON object: {"tool":"<tool_name>","args":{"key":"value"}}',
            (
                '- When the turn requires multiple tool calls, return exactly one JSON object: '
                '{"content":"","tool_calls":[{"tool":"<tool_name>","args":{"key":"value"}}]}'
            ),
            "- Do not use markdown fences, labels, or backticks around tool-call JSON.",
            "- Escape newline characters inside string values; the JSON must parse without repair.",
            "- Do not emit partial or truncated JSON objects.",
        ]

    @staticmethod
    def compile(
        skill: SkillConfig,
        dialect: DialectConfig,
        next_member: str | None = None,
        patch: str | None = None,
        protocol_governed_enabled: bool = False,
    ) -> str:
        prompt = f"IDENTITY: {skill.name}\n"
        prompt += f"INTENT: {skill.intent}\n\n"

        prompt += "RESPONSIBILITIES:\n"
        for r in skill.responsibilities:
            prompt += f"- {r}\n"

        if skill.idesign_constraints:
            prompt += "\nSTRUCTURAL CONSTRAINTS (Optional):\n"
            for c in skill.idesign_constraints or []:
                prompt += f"- {c}\n"

        prompt += "\nCARD SYSTEM PROTOCOL:\n"
        prompt += "- You MAY call 'get_issue_context' to read comment history and intent.\n"
        prompt += "- A context-only response is invalid: do not stop after get_issue_context/read-only actions.\n"
        prompt += "- Use 'add_issue_comment' to log your progress, reasoning, and final handoff memo.\n"
        prompt += "- The Card System is the Source of Truth for INTENT. Files are the result of EXECUTION.\n"
        for line in PromptCompiler._protocol_lines(protocol_governed_enabled):
            prompt += f"{line}\n"
        prompt += (
            "- If no valid action is possible, emit exactly one tool call to "
            "'add_issue_comment' explaining the blocker.\n"
        )
        if skill.tools:
            prompt += "\nALLOWED TOOLS:\n"
            for t in skill.tools:
                prompt += f"- {t}\n"

        prompt += "\nTOOL ARGUMENT CONTRACT:\n"
        prompt += "- write_file args MUST include: path (string), content (string)\n"
        prompt += "- read_file args MUST include: path (string)\n"
        prompt += "- add_issue_comment args MUST include: comment (string)\n"
        prompt += "- update_issue_status args MUST include: status (string)\n"
        prompt += (
            "- If update_issue_status.status is 'blocked', args MUST include "
            "wait_reason in: resource|dependency|review|input|system\n"
        )
        prompt += "- get_issue_context args MAY be {}\n"
        prompt += (
            "- If Execution Context JSON includes required_action_tools, your "
            "turn is INVALID unless all listed tools are called.\n"
        )
        prompt += (
            "- If Execution Context JSON includes required_statuses, your "
            "update_issue_status.status MUST be one of them.\n"
        )
        if protocol_governed_enabled:
            prompt += '- Return ONLY one JSON object matching {"content":"","tool_calls":[...]}.\n'
            prompt += "- Do not wrap the JSON object in markdown fences.\n"
        else:
            prompt += (
                '- Return ONLY compact JSON with no markdown fences or prose. '
                'If more than one tool call is needed, use {"content":"","tool_calls":[...]}.\n'
            )

        role_name = (skill.name or "").strip().lower()
        if role_name in {"requirements_analyst", "architect", "coder", "developer", "code_reviewer", "integrity_guard"}:
            prompt += "\nTURN COMPLETION CONTRACT:\n"
            role_contracts = {
                "requirements_analyst": [
                    "You MUST write requirements content using write_file(path='agent_output/requirements.txt', ...).",
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "architect": [
                    "You MUST write architecture decision JSON using write_file(path='agent_output/design.txt', ...).",
                    "That JSON MUST include recommendation, confidence, and evidence keys.",
                    (
                        "evidence MUST include: estimated_domains, "
                        "external_integrations, independent_scaling_needs, "
                        "deployment_complexity, team_parallelism, operational_maturity."
                    ),
                    (
                        "If the turn contract specifies frontend_framework, "
                        "include frontend_framework in the same JSON object."
                    ),
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "coder": [
                    (
                        "You MUST write implementation code using write_file(path='<one of the required write paths "
                        "from the Write Path Contract>', ...)."
                    ),
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "developer": [
                    (
                        "You MUST write implementation code using write_file(path='<one of the required write paths "
                        "from the Write Path Contract>', ...)."
                    ),
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "code_reviewer": [
                    (
                        "You MUST read every path listed in the Read Path "
                        "Contract with read_file(...) in this same response."
                    ),
                    "Do not stop after reading only a subset of required artifacts.",
                    "You MUST then call update_issue_status(status='code_review') for guard handoff.",
                ],
                "integrity_guard": [
                    "You MUST produce a terminal guard decision by calling update_issue_status.",
                    "Valid terminal outcomes are done or blocked.",
                    "If you choose blocked, you MUST include wait_reason: resource|dependency|review|input|system.",
                ],
            }
            for line in role_contracts.get(role_name, []):
                prompt += f"- {line}\n"

        prompt += f"\nSYNTAX DIALECT ({dialect.model_family}):\n"
        prompt += f"You MUST use this format for all file operations:\n{dialect.dsl_format}\n"

        prompt += "\nCONSTRAINTS:\n"
        for c in dialect.constraints:
            prompt += f"- {c}\n"

        prompt += f"\nGUARDRAIL: {dialect.hallucination_guard}\n"

        if next_member:
            prompt += "\nWARM HANDOFF PROTOCOL:\n"
            prompt += f"Your work will be handed off to the '{next_member}'.\n"
            prompt += "You MUST include a 'Member-to-Member Memo' in an 'add_issue_comment' call.\n"

        if patch:
            prompt += f"\n\nPATCH:\n{patch}"

        return prompt
