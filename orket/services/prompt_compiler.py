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
        prompt += "- ALWAYS start by calling 'get_issue_context' to read the comment history and intent.\n"
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
        prompt += "- get_issue_context args MAY be {}\n"
        prompt += "- Return ONLY JSON tool blocks. No markdown explanations outside tool blocks.\n"

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
