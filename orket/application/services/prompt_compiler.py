from __future__ import annotations
from typing import List, Optional
from orket.schema import SkillConfig, DialectConfig

class PromptCompiler:
    """
    Service responsible for assembling the final system instruction string.
    Implements iDesign structural constraints and card system protocols.
    """
    
    @staticmethod
    def compile(skill: SkillConfig, dialect: DialectConfig, next_member: Optional[str] = None, patch: Optional[str] = None) -> str:
        prompt = f"IDENTITY: {skill.name}\n"
        prompt += f"INTENT: {skill.intent}\n\n"
        
        prompt += "RESPONSIBILITIES:\n"
        for r in skill.responsibilities:
            prompt += f"- {r}\n"

        prompt += "\niDESIGN CONSTRAINTS (Structural Integrity):\n"
        idesign_standard = [
            "Maintain strict separation of concerns: Managers, Engines, Accessors, Utilities.",
            "Managers orchestrate the workflow and high-level logic.",
            "Engines handle complex computations or business rules.",
            "Accessors manage state or external tool interactions.",
            "Utilities provide cross-cutting logic.",
            "Organize files into: /controllers, /managers, /engines, /accessors, /utils, /tests."
        ]
        for c in (idesign_standard + (skill.idesign_constraints or [])):
            prompt += f"- {c}\n"

        prompt += "\nCARD SYSTEM PROTOCOL:\n"
        prompt += "- You MAY call 'get_issue_context' to read comment history and intent.\n"
        prompt += "- A context-only response is invalid: do not stop after get_issue_context/read-only actions.\n"
        prompt += "- Use 'add_issue_comment' to log your progress, reasoning, and final handoff memo.\n"
        prompt += "- The Card System is the Source of Truth for INTENT. Files are the result of EXECUTION.\n"
        prompt += "- DO NOT narrate your plan in prose. Emit executable tool-call JSON blocks only.\n"
        prompt += "- Every action must be emitted as:\n"
        prompt += "  ```json\n"
        prompt += "  {\"tool\": \"<tool_name>\", \"args\": {\"key\": \"value\"}}\n"
        prompt += "  ```\n"
        prompt += "- If no valid action is possible, emit exactly one tool call to 'add_issue_comment' explaining the blocker.\n"
        if skill.tools:
            prompt += "\nALLOWED TOOLS:\n"
            for t in skill.tools:
                prompt += f"- {t}\n"

        prompt += "\nTOOL ARGUMENT CONTRACT:\n"
        prompt += "- write_file args MUST include: path (string), content (string)\n"
        prompt += "- read_file args MUST include: path (string)\n"
        prompt += "- add_issue_comment args MUST include: comment (string)\n"
        prompt += "- update_issue_status args MUST include: status (string)\n"
        prompt += "- If update_issue_status.status is 'blocked', args MUST include wait_reason in: resource|dependency|review|input|system\n"
        prompt += "- get_issue_context args MAY be {}\n"
        prompt += "- If Execution Context JSON includes required_action_tools, your turn is INVALID unless all listed tools are called.\n"
        prompt += "- If Execution Context JSON includes required_statuses, your update_issue_status.status MUST be one of them.\n"
        prompt += "- Return ONLY JSON tool blocks. No markdown explanations outside tool blocks.\n"

        role_name = (skill.name or "").strip().lower()
        if role_name in {"requirements_analyst", "architect", "coder", "developer", "code_reviewer", "integrity_guard"}:
            prompt += "\nTURN COMPLETION CONTRACT:\n"
            role_contracts = {
                "requirements_analyst": [
                    "You MUST write requirements content using write_file(path='agent_output/requirements.txt', ...).",
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "architect": [
                    "You MUST write design content using write_file(path='agent_output/design.txt', ...).",
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "coder": [
                    "You MUST write implementation code using write_file(path='agent_output/main.py', ...).",
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "developer": [
                    "You MUST write implementation code using write_file(path='agent_output/main.py', ...).",
                    "You MUST then call update_issue_status(status='code_review').",
                ],
                "code_reviewer": [
                    "You MUST read required implementation artifacts with read_file(...).",
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
            prompt += f"\nWARM HANDOFF PROTOCOL:\n"
            prompt += f"Your work will be handed off to the '{next_member}'.\n"
            prompt += f"You MUST include a 'Member-to-Member Memo' in an 'add_issue_comment' call.\n"

        if patch:
            prompt += f"\n\nPATCH:\n{patch}"
            
        return prompt
