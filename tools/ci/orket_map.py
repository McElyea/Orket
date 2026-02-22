#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from typing import Any

STAGES = ["base_shape", "dto_links", "relationship_vocabulary", "policy", "determinism"]

EVENT_RE = re.compile(
    r"\[(?P<lvl>\w+)\] "
    r"\[STAGE:(?P<stg>[\w_]+)\] "
    r"\[CODE:(?P<code>[\w_]+)\] "
    r"\[LOC:(?P<loc>[^\]]+)\] "
    r"(?P<msg>.*?) \| (?P<det>.*)"
)


def sanitize_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)


def _unescape_legacy(value: str) -> str:
    return value.replace(r"\u007c", "|").replace(r"\r", "\r").replace(r"\n", "\n")


def _parse_details_v1(detail_text: str) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if not detail_text.strip():
        return details
    for token in detail_text.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        details[key] = _unescape_legacy(value)
    return details


def _parse_details(detail_text: str) -> dict[str, Any]:
    text = detail_text.strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return _parse_details_v1(text)
        if isinstance(parsed, dict):
            return parsed
        return {"_detail": parsed}
    return _parse_details_v1(text)


def _stem_from_loc(stage: str, loc: str) -> str:
    if stage == "ci" and loc.startswith("/ci/diff/"):
        tail = loc.split("/ci/diff/", 1)[1]
        return tail or "global"
    return "global"


def build_matrix(log_lines: list[str]) -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = {}

    for line in log_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("[SUMMARY]"):
            continue

        match = EVENT_RE.fullmatch(stripped)
        if not match:
            continue

        stage = match.group("stg")
        level = match.group("lvl")
        loc = match.group("loc")
        details = _parse_details(match.group("det"))

        stem = str(details.get("stem") or _stem_from_loc(stage, loc))
        if stem not in matrix:
            matrix[stem] = {stage_name: "UNSEEN" for stage_name in STAGES}

        if stage in STAGES:
            if level == "FAIL":
                matrix[stem][stage] = "FAIL"
            elif matrix[stem][stage] != "FAIL":
                matrix[stem][stage] = "PASS"

    return matrix


def emit_mermaid(matrix: dict[str, dict[str, str]]) -> None:
    print("```mermaid")
    print("flowchart TB")

    for stem in sorted(matrix):
        if stem == "global":
            continue
        safe_stem = sanitize_id(stem)
        print(f"    subgraph {safe_stem} [Stem: {stem}]")
        print("        direction BT")

        prev_node: str | None = None
        for stage in STAGES:
            node_id = f"{safe_stem}_{stage}"
            status = matrix[stem][stage]
            style = "fill:#222,stroke:#444,color:#888"
            if status == "PASS":
                style = "fill:#064a16,stroke:#00ff00,color:#fff"
            if status == "FAIL":
                style = "fill:#610c0c,stroke:#ff0000,color:#fff"

            print(f"        {node_id}[{stage}]")
            print(f"        style {node_id} {style}")
            if prev_node is not None:
                print(f"        {prev_node} --- {node_id}")
            prev_node = node_id
        print("    end")

    print("```")


def main() -> int:
    matrix = build_matrix(sys.stdin.readlines())
    emit_mermaid(matrix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
