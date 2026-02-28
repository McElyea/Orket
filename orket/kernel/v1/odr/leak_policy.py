from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .parsers import normalize_newlines

DEFAULT_CODE_LEAK_PATTERNS = [
    r"(?s)```(?:[^\n]*)\n.*?\n```",
    r"\b(def|class|import|fn|let|const|interface|type)\b",
    r"\b(npm|pip|cargo|docker|venv|node_modules)\b",
]
DEFAULT_LEAK_GATE_MODE = "balanced_v1"
VALID_LEAK_GATE_MODES = {"strict", "balanced_v1"}

_WEAK_TOKENS = ("type", "interface", "schema", "contract", "signature", "struct")
_WEAK_STRICT_SET = {"type", "interface"}
_TOOLING_TOKENS = ("npm", "pip", "cargo", "docker", "venv", "node_modules", "node", "bash", "sh")

_PY_PATTERNS = (
    re.compile(r"(?m)^\s*(?:[-*]\s+)?def\s+[A-Za-z_]\w*\s*\("),
    re.compile(r"(?m)^\s*(?:[-*]\s+)?class\s+[A-Za-z_]\w*\s*[:\(]"),
    re.compile(r"(?m)^\s*(?:[-*]\s+)?(from\s+\w[\w\.]*\s+import|import\s+\w)"),
)
_JS_TS_PATTERNS = (
    re.compile(r"(?m)^\s*(?:[-*]\s+)?interface\s+[A-Za-z_]\w*\b"),
    re.compile(r"(?m)^\s*(?:[-*]\s+)?type\s+[A-Za-z_]\w*\s*="),
    re.compile(r"(?m)^\s*(?:[-*]\s+)?(const|let|var)\s+[A-Za-z_]\w*\s*="),
    re.compile(r"(?m)^\s*(?:[-*]\s+)?function\s+[A-Za-z_]\w*\s*\("),
)
_TOOLING_PATTERN = re.compile(
    rf"\b({'|'.join(re.escape(token) for token in _TOOLING_TOKENS)})\b",
    flags=re.IGNORECASE,
)
_CLI_MARKER_PATTERNS = (
    re.compile(r"--\w"),
    re.compile(r"-\w"),
    re.compile(r"&&|\|\||\|"),
    re.compile(r"\$\s*\w"),
    re.compile(r"\bpython\s+-m\b", flags=re.IGNORECASE),
    re.compile(r"\b(node|bash|sh)\b", flags=re.IGNORECASE),
)
_EXEC_VERB_PATTERN = re.compile(r"\b(run|install|execute)\b", flags=re.IGNORECASE)
_INDENT_BLOCK_PATTERN = re.compile(r"(?m)^(?: {4,}|\t).+\n(?: {4,}|\t).+")
_CALL_PATTERN = re.compile(r"\b\w+\s*\([^)]*\)")


@dataclass(frozen=True)
class LeakDetection:
    hard_leak: bool
    matches_hard: list[str]
    matches_weak: list[dict[str, str]]
    classes: list[str]
    warnings: list[str]

    def as_trace_fields(self) -> dict[str, Any]:
        return {
            "code_leak_matches_hard": list(self.matches_hard),
            "code_leak_matches_weak": [dict(item) for item in self.matches_weak],
            "code_leak_warning_count": len(self.warnings),
            "code_leak_classes": list(self.classes),
            "code_leak_warnings": list(self.warnings),
        }


def _snippet(text: str, start: int, end: int, max_chars: int = 120) -> str:
    center = max(0, min(len(text), (start + end) // 2))
    half = max_chars // 2
    lo = max(0, center - half)
    hi = min(len(text), center + half)
    raw = text[lo:hi].strip().replace("\r\n", "\n").replace("\r", "\n")
    escaped = raw.replace("\n", "\\n")
    return escaped[:max_chars]


def _strip_list_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("- ") or stripped.startswith("* "):
        return stripped[2:].lstrip()
    return stripped


def _is_fence_open(line: str) -> bool:
    stripped = _strip_list_prefix(line)
    return stripped.startswith("```") and not stripped.startswith("````")


def _is_fence_close(line: str) -> bool:
    stripped = _strip_list_prefix(line)
    if not stripped.startswith("```") or stripped.startswith("````"):
        return False
    return stripped[3:].strip() == ""


def _has_fence_block(text: str) -> bool:
    lines = normalize_newlines(text).split("\n")
    for index, line in enumerate(lines):
        if not _is_fence_open(line):
            continue
        for candidate in lines[index + 1 :]:
            if _is_fence_close(candidate):
                return True
    return False


def _has_cli_context(fragment: str) -> bool:
    return any(pattern.search(fragment) for pattern in _CLI_MARKER_PATTERNS) or _EXEC_VERB_PATTERN.search(fragment) is not None


def _tooling_hard_matches(text: str) -> tuple[list[str], list[dict[str, str]]]:
    hard: list[str] = []
    weak: list[dict[str, str]] = []
    for match in _TOOLING_PATTERN.finditer(text):
        token = str(match.group(1) or "").lower()
        start, end = match.span()
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        if line_end == -1:
            line_end = len(text)
        same_line = text[line_start:line_end]
        around = text[max(0, start - 80) : min(len(text), end + 80)]
        if _has_cli_context(same_line) or _has_cli_context(around):
            hard.append(f"tooling_context:{token}")
        else:
            weak.append(
                {
                    "token": token,
                    "detector": "tooling_without_context",
                    "context_snippet": _snippet(text, start, end),
                }
            )
    return hard, weak


def _weak_token_matches(text: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for token in _WEAK_TOKENS:
        for match in re.finditer(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE):
            matches.append(
                {
                    "token": token,
                    "detector": "weak_token",
                    "context_snippet": _snippet(text, match.start(), match.end()),
                }
            )
    return matches


def _fallback_signal_summary(text: str) -> tuple[int, dict[str, bool]]:
    has_braces_pair = ("{" in text) and ("}" in text)
    semicolons_ge_two = text.count(";") >= 2
    equals_ge_two = text.count("=") >= 2
    call_like = _CALL_PATTERN.search(text) is not None
    arrow = ("->" in text) or ("=>" in text)
    indent_block = _INDENT_BLOCK_PATTERN.search(text) is not None
    signals = {
        "braces_pair": has_braces_pair,
        "semicolons_ge_two": semicolons_ge_two,
        "equals_ge_two": equals_ge_two,
        "call_like": call_like,
        "arrow": arrow,
        "indentation_block": indent_block,
    }
    return sum(1 for value in signals.values() if value), signals


def detect_code_leak(
    *,
    architect_raw: str,
    auditor_raw: str,
    mode: str,
    patterns: list[str] | None = None,
) -> LeakDetection:
    normalized_architect_raw = normalize_newlines(architect_raw)
    normalized_auditor_raw = normalize_newlines(auditor_raw)
    combined = f"{normalized_architect_raw}\n{normalized_auditor_raw}"
    selected_mode = mode if mode in VALID_LEAK_GATE_MODES else DEFAULT_LEAK_GATE_MODE
    configured = list(DEFAULT_CODE_LEAK_PATTERNS) if patterns is None else list(patterns)

    if selected_mode == "strict":
        hard = []
        for index, pattern in enumerate(configured):
            if re.search(pattern, combined) is not None:
                hard.append(f"strict_pattern_{index}")
        return LeakDetection(
            hard_leak=bool(hard),
            matches_hard=hard,
            matches_weak=[],
            classes=(["CODE"] if hard else []),
            warnings=[],
        )

    hard: list[str] = []
    weak = _weak_token_matches(combined)
    classes: list[str] = []
    warnings: list[str] = []

    if _has_fence_block(combined):
        hard.append("fence_block")
        classes.append("FENCE")

    for pattern in _PY_PATTERNS:
        if pattern.search(combined) is not None:
            hard.append(f"python_struct:{pattern.pattern}")
    for pattern in _JS_TS_PATTERNS:
        if pattern.search(combined) is not None:
            hard.append(f"js_ts_struct:{pattern.pattern}")
    if any(item.startswith("python_struct:") or item.startswith("js_ts_struct:") for item in hard):
        classes.append("CODE")

    tooling_hard, tooling_weak = _tooling_hard_matches(combined)
    if tooling_hard:
        hard.extend(tooling_hard)
        classes.append("TOOLING")
    weak.extend(tooling_weak)

    # Fallback only when no hard signals are present yet.
    if not hard:
        signal_count, signal_map = _fallback_signal_summary(combined)
        structural = bool(
            signal_map["indentation_block"] or signal_map["braces_pair"] or signal_map["semicolons_ge_two"]
        )
        if signal_count >= 3 and structural:
            hard.append("fallback_structural_signals")
            classes.append("CODE")

    # Warnings for strict weak tokens.
    for row in weak:
        token = str(row.get("token") or "").lower()
        if token in _WEAK_STRICT_SET:
            warnings.append(f"WARN_LEAK_WEAK_TOKEN:{token}")
        elif token:
            warnings.append(f"WARN_LEAK_OBSERVED_TOKEN:{token}")
    # Deduplicate warnings while preserving order.
    dedup_warnings: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        dedup_warnings.append(warning)

    dedup_classes = list(dict.fromkeys(classes))
    return LeakDetection(
        hard_leak=bool(hard),
        matches_hard=list(dict.fromkeys(hard)),
        matches_weak=weak,
        classes=dedup_classes,
        warnings=dedup_warnings,
    )
