from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Optional

from orket.logging import log_event


class DriverConversationMixin:
    def _should_handle_as_conversation(self, message: str) -> bool:
        text = str(message or "").strip().lower()
        if not text:
            return True
        if len(text) <= 3:
            return True

        conversation_patterns = (
            r"^(hi|hey|hello|yo|sup|how are you)\b",
            r"\bthank(s| you)\b",
            r"\bcan you (chat|talk|converse)\b",
            r"\byou are not set up to converse\b",
            r"\blet('?s| us) chat\b",
        )
        for pattern in conversation_patterns:
            if re.search(pattern, text):
                return True

        structural_markers = (
            "create epic",
            "create issue",
            "create rock",
            "add card",
            "list cards",
            "/add-card",
            "/list-cards",
            "new epic",
            "new issue",
            "new rock",
            "adopt issue",
            "move issue",
            "assign team",
            "run active",
            "halt session",
            "archive card",
            "runtime policy",
            "settings",
        )
        return not any(marker in text for marker in structural_markers)

    def _has_explicit_structural_intent(self, message: str) -> bool:
        text = str(message or "").strip().lower()
        if not text:
            return False

        explicit_patterns = (
            r"^/(create|add-card|add_card|list-cards|list_cards|show|list)\b",
            r"\b(create|add|move|adopt|archive|delete|update|run|halt)\b.{0,40}\b(epic|issue|rock|card|session|team|environment)\b",
            r"\b(make|perform|do)\b.{0,40}\b(board|structural)\b.{0,20}\b(change|action)\b",
        )
        return any(re.search(pattern, text) for pattern in explicit_patterns)

    def _conversation_reply(self, message: str) -> Optional[str]:
        text = str(message or "").strip()
        if not text:
            return "I am here. You can chat with me or ask me to make a specific board change."

        lowered = text.lower()
        if "what can you do" in lowered or "capabilities" in lowered or "in this environment" in lowered:
            return self._capabilities_summary()
        if (
            "tell me about this application" in lowered
            or "about this app" in lowered
            or "about this application" in lowered
            or "what is this application" in lowered
            or "what is this app" in lowered
        ):
            return (
                "This is Orket, an orchestration application for managing rocks, epics, cards, teams, and "
                "runtime policy. I can converse and I can operate the board through CLI-style commands like "
                "/list, /show, /create, /list-cards, and /add-card."
            )
        if re.search(r"\bcan you\b.*\b(converse|talk|chat)\b", lowered):
            return (
                "Yes. I can converse normally and also run Orket operations when you ask explicitly."
            )
        if lowered in {"what?", "what"}:
            return "I can explain capabilities, answer simple questions, and run explicit Orket CLI commands."
        if "didn't think so" in lowered:
            return "Fair pushback. Ask me anything and I will answer directly; use /help for command capabilities."
        if lowered in {"hi", "hey", "hello"}:
            return "Hi. I am here and can chat normally. If you want structural changes, ask explicitly."
        if lowered in {"cool", "nice", "great", "awesome"}:
            return "Nice. Want to keep chatting, or switch to a board action?"
        if "not set up to converse" in lowered:
            return "I can converse. I will only make structural changes when you ask for them explicitly."
        if "anything else" in lowered or "say anything else" in lowered:
            return "Yes. Ask about capabilities with /help, inspect assets with /list, or ask a direct question."
        math_answer = self._try_answer_math(text)
        if math_answer is not None:
            return math_answer
        return None

    async def _conversation_model_reply(self, message: str) -> Optional[str]:
        complete_fn = getattr(self.provider, "complete", None)
        if not callable(complete_fn):
            return None
        try:
            response = await complete_fn(
                [
                    {"role": "system", "content": self._conversation_system_prompt()},
                    {"role": "user", "content": message},
                ]
            )
            content = str(getattr(response, "content", "") or "").strip()
            if not content:
                return None
            return self._normalize_conversation_model_output(content)
        except (RuntimeError, ValueError, TypeError, KeyError, OSError):
            return None

    def _conversation_system_prompt(self) -> str:
        return (
            "You are the Orket Operator conversational assistant. "
            "Chat naturally, clearly, and briefly. "
            "Do not produce JSON, plans, or structural board mutations. "
            "If the user asks for structural actions, ask them to request explicitly with Orket CLI commands."
        )

    def _normalize_conversation_model_output(self, content: str) -> str:
        text = content.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return text
            response = str(payload.get("response", "") or "").strip()
            reasoning = str(payload.get("reasoning", "") or "").strip()
            if response:
                return response
            if reasoning:
                return reasoning
        return text

    def _capabilities_summary(self) -> str:
        departments = sorted([p.name for p in self.model_root.iterdir() if p.is_dir()]) if self.model_root.exists() else []
        summary = [self._cli_help_text()]
        if departments:
            summary.append(f"Detected departments: {', '.join(departments)}")
        summary.append("Conversation mode is on by default. I only run structural actions when explicitly requested.")
        return "\n".join(summary)

    def _log_operator_metric(self, metric_name: str, **tags: Any) -> None:
        try:
            payload = {"metric": metric_name, "value": 1, "tags": tags}
            log_event("operator_metric", payload, Path("workspace/default"), role="DRIVER")
        except (RuntimeError, ValueError, OSError):
            return

    def _try_answer_math(self, message: str) -> str | None:
        lowered = str(message or "").strip().lower()
        prefixes = ("what is ", "what's ", "calculate ", "compute ")
        expr = lowered
        for prefix in prefixes:
            if expr.startswith(prefix):
                expr = expr[len(prefix):]
                break
        expr = expr.strip().rstrip("?").strip()
        if not expr:
            return None

        if not re.fullmatch(r"[0-9\.\+\-\*\/\(\)\s]+", expr):
            return None

        try:
            node = ast.parse(expr, mode="eval")
        except SyntaxError:
            return None
        try:
            value = self._eval_arithmetic(node.body)
        except (ValueError, ZeroDivisionError):
            return None

        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)

    def _eval_arithmetic(self, node: ast.AST) -> float:
        if isinstance(node, ast.BinOp):
            left = self._eval_arithmetic(node.left)
            right = self._eval_arithmetic(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            raise ValueError("Unsupported arithmetic operator")
        if isinstance(node, ast.UnaryOp):
            value = self._eval_arithmetic(node.operand)
            if isinstance(node.op, ast.UAdd):
                return value
            if isinstance(node.op, ast.USub):
                return -value
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Unsupported expression")
