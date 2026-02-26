from __future__ import annotations

from typing import Any, Dict, List, Tuple


ARCHITECT_HEADERS = [
    "### REQUIREMENT",
    "### CHANGELOG",
    "### ASSUMPTIONS",
    "### OPEN_QUESTIONS",
]

AUDITOR_HEADERS = [
    "### CRITIQUE",
    "### PATCHES",
    "### EDGE_CASES",
    "### TEST_GAPS",
]


def normalize_newlines(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _err(code: str, message: str) -> Dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}}


def _extract_sections(text: str, required_headers: List[str]) -> Tuple[Dict[str, str], Dict[str, Any] | None]:
    normalized = normalize_newlines(text)
    if not normalized.strip():
        return {}, _err("EMPTY_INPUT", "Input text is empty.")

    lines = normalized.split("\n")
    positions: Dict[str, List[int]] = {header: [] for header in required_headers}
    lower_lookup = {header.lower(): header for header in required_headers}

    for idx, line in enumerate(lines):
        stripped = line.strip().lower()
        matched = lower_lookup.get(stripped)
        if matched is not None:
            positions[matched].append(idx)

    for header, hits in positions.items():
        if len(hits) > 1:
            return {}, _err("DUPLICATE_HEADER", f"Duplicate header detected: {header}")

    found_order = [header for header in required_headers if positions[header]]
    missing = [header for header in required_headers if not positions[header]]
    if missing:
        return {}, _err("MISSING_HEADER", f"Missing required header(s): {', '.join(missing)}")

    found_by_position = sorted(
        ((positions[header][0], header) for header in required_headers),
        key=lambda item: item[0],
    )
    found_sequence = [header for _pos, header in found_by_position]
    if found_sequence != required_headers:
        return {}, _err(
            "HEADER_OUT_OF_ORDER",
            "Required headers are out of order. "
            f"expected={required_headers} found={found_sequence}",
        )

    sections: Dict[str, str] = {}
    for idx, header in enumerate(required_headers):
        start = positions[header][0] + 1
        end = len(lines) if idx == len(required_headers) - 1 else positions[required_headers[idx + 1]][0]
        chunk = "\n".join(lines[start:end]).strip()
        sections[header] = chunk
    return sections, None


def _to_list(section_text: str) -> List[str]:
    rows: List[str] = []
    for line in normalize_newlines(section_text).split("\n"):
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith("-"):
            item = trimmed[1:].strip()
            if item:
                rows.append(item)
            continue
        rows.append(trimmed)
    return rows


def parse_architect(text: str) -> Dict[str, Any]:
    sections, error = _extract_sections(text, ARCHITECT_HEADERS)
    if error is not None:
        return error

    requirement = sections["### REQUIREMENT"].strip()
    if not requirement:
        return _err("EMPTY_REQUIREMENT", "### REQUIREMENT section must contain non-whitespace text.")

    return _ok(
        {
            "requirement": requirement,
            "changelog": _to_list(sections["### CHANGELOG"]),
            "assumptions": _to_list(sections["### ASSUMPTIONS"]),
            "open_questions": _to_list(sections["### OPEN_QUESTIONS"]),
        }
    )


def parse_auditor(text: str) -> Dict[str, Any]:
    sections, error = _extract_sections(text, AUDITOR_HEADERS)
    if error is not None:
        return error

    return _ok(
        {
            "critique": _to_list(sections["### CRITIQUE"]),
            "patches": _to_list(sections["### PATCHES"]),
            "edge_cases": _to_list(sections["### EDGE_CASES"]),
            "test_gaps": _to_list(sections["### TEST_GAPS"]),
        }
    )
