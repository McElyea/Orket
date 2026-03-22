from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import _payload_digest
from scripts.odr.context_continuity_lane import DEFAULT_LANE_CONFIG_PATH, load_lane_config, load_v0_replay_contract

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _WHITESPACE_RE.sub(" ", text).strip()


def _trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    limit = max(1, max_chars - 3)
    return text[:limit].rstrip() + "..."


def _contract(config_path: Path | None = None) -> tuple[dict[str, Any], Path]:
    config = load_lane_config(config_path or DEFAULT_LANE_CONFIG_PATH)
    path = Path(str(config["v0_replay_contract_path"]))
    return load_v0_replay_contract(config), path


def _select_items(source_history: list[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = {str(item) for item in list(contract.get("allowed_source_kinds") or [])}
    excluded = {str(item) for item in list(contract.get("excluded_source_kinds") or [])}

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in source_history:
        artifact_id = str(raw.get("artifact_id") or "").strip()
        artifact_kind = str(raw.get("artifact_kind") or "").strip()
        if not artifact_id or not artifact_kind:
            raise ValueError("V0 replay source history entries must declare artifact_id and artifact_kind.")
        if artifact_kind in excluded:
            raise ValueError(f"V0 replay source history kind is explicitly excluded: {artifact_kind}.")
        if artifact_kind not in allowed:
            raise ValueError(f"V0 replay source history kind is not allowed by the contract: {artifact_kind}.")

        authority_level = str(raw.get("authority_level") or "").strip()
        if authority_level and authority_level != "authoritative":
            raise ValueError("V0 replay source history may not load non-authoritative items.")

        has_content = "content" in raw
        has_payload = "payload" in raw
        if has_content == has_payload:
            raise ValueError(f"V0 replay source history {artifact_id} must declare exactly one of content or payload.")
        body = raw["content"] if has_content else raw["payload"]
        normalized_body = _normalize_text(body)
        dedupe_key = (artifact_kind, normalized_body)
        candidate = {
            "artifact_id": artifact_id,
            "artifact_kind": artifact_kind,
            "artifact_body": body,
            "round_index": int(raw.get("round_index") or 0),
        }
        incumbent = deduped.get(dedupe_key)
        if incumbent is None:
            deduped[dedupe_key] = candidate
            continue
        incumbent_key = (-int(incumbent["round_index"]), str(incumbent["artifact_id"]))
        candidate_key = (-int(candidate["round_index"]), str(candidate["artifact_id"]))
        if candidate_key < incumbent_key:
            deduped[dedupe_key] = candidate

    kind_precedence = [str(item) for item in list(contract.get("source_ordering", {}).get("kind_precedence") or [])]
    per_kind_limit = {
        str(key): int(value)
        for key, value in dict(contract.get("per_kind_item_limit") or {}).items()
    }
    grouped: dict[str, list[dict[str, Any]]] = {kind: [] for kind in kind_precedence}
    for item in deduped.values():
        grouped.setdefault(str(item["artifact_kind"]), []).append(item)
    for kind_items in grouped.values():
        kind_items.sort(key=lambda item: (-int(item["round_index"]), str(item["artifact_id"])))

    selected: list[dict[str, Any]] = []
    for kind in kind_precedence:
        selected.extend(grouped.get(kind, [])[: max(0, per_kind_limit.get(kind, 0))])
    return selected


def _candidate_sections(selected_items: list[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    max_chars = int(dict(contract.get("truncation_policy") or {}).get("max_text_chars_per_item") or 220)
    section_headers = {
        str(key): str(value)
        for key, value in dict(contract.get("formatting_template", {}).get("section_headers") or {}).items()
    }
    inclusion_order = [str(item) for item in list(contract.get("inclusion_precedence") or [])]

    by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in inclusion_order}
    for item in selected_items:
        by_kind.setdefault(str(item["artifact_kind"]), []).append(item)

    sections: list[dict[str, Any]] = []
    for kind in inclusion_order:
        items = by_kind.get(kind, [])
        if not items:
            continue
        lines = [
            f"- {_trim_text(_normalize_text(item['artifact_body']), max_chars)}"
            for item in items
        ]
        sections.append(
            {
                "kind": kind,
                "header": section_headers.get(kind, kind),
                "lines": lines,
                "source_history_refs": [str(item["artifact_id"]) for item in items],
            }
        )

    latest_arch = next(
        (_normalize_text(item["artifact_body"]) for item in selected_items if item["artifact_kind"] == "latest_architect_delta"),
        "",
    )
    latest_audit = next(
        (_normalize_text(item["artifact_body"]) for item in selected_items if item["artifact_kind"] == "latest_auditor_critique"),
        "",
    )
    if latest_arch or latest_audit:
        template = list(dict(contract.get("causal_summary_rule") or {}).get("template") or [])
        causal_lines: list[str] = []
        if latest_arch and template:
            causal_lines.append(f"- {template[0].format(latest_architect_delta=_trim_text(latest_arch, max_chars))}")
        if latest_audit and len(template) > 1:
            causal_lines.append(f"- {template[1].format(latest_auditor_critique=_trim_text(latest_audit, max_chars))}")
        sections.append(
            {
                "kind": "causal_summary",
                "header": section_headers.get("causal_summary", "Causal Summary"),
                "lines": causal_lines,
                "source_history_refs": [
                    str(item["artifact_id"])
                    for item in selected_items
                    if item["artifact_kind"] in {"latest_architect_delta", "latest_auditor_critique"}
                ],
            }
        )
    return sections


def _format_sections(sections: list[dict[str, Any]], contract: dict[str, Any]) -> str:
    title = str(dict(contract.get("formatting_template") or {}).get("title") or "### REPLAY BLOCK")
    blocks = [title]
    for section in sections:
        if not section["lines"]:
            continue
        blocks.append(f"#### {section['header']}")
        blocks.extend(str(line) for line in section["lines"])
    return "\n".join(blocks).strip()


def build_v0_replay_block(
    source_history: list[dict[str, Any]],
    *,
    artifact_id: str,
    config_path: Path | None = None,
) -> dict[str, Any]:
    contract, contract_path = _contract(config_path)
    selected = _select_items(source_history, contract)
    sections = _candidate_sections(selected, contract)

    truncation = dict(contract.get("truncation_policy") or {})
    max_bytes = int(truncation.get("max_utf8_bytes") or 1200)
    required_kinds = {str(item) for item in list(truncation.get("always_include_kinds") or [])}
    drop_order = [str(item) for item in list(truncation.get("drop_order_low_to_high_precedence") or [])]

    formatted = _format_sections(sections, contract)
    while len(formatted.encode("utf-8")) > max_bytes:
        dropped = False
        for kind in drop_order:
            for section in sections:
                if section["kind"] != kind or not section["lines"]:
                    continue
                if kind in required_kinds:
                    continue
                section["lines"].pop()
                if section["source_history_refs"]:
                    section["source_history_refs"].pop()
                dropped = True
                break
            if dropped:
                break
        if not dropped:
            raise ValueError("V0 replay block exceeds the locked truncation budget after dropping non-required items.")
        sections = [section for section in sections if section["lines"]]
        formatted = _format_sections(sections, contract)

    source_history_refs: list[str] = []
    for section in sections:
        for ref in list(section.get("source_history_refs") or []):
            if ref not in source_history_refs:
                source_history_refs.append(ref)

    return {
        "artifact_id": artifact_id,
        "artifact_kind": "bounded_replay_block",
        "content": formatted,
        "artifact_sha256": _payload_digest({"artifact": formatted}),
        "utf8_bytes": len(formatted.encode("utf-8")),
        "source_history_refs": source_history_refs,
        "builder_contract_path": str(contract_path),
        "builder_contract_sha256": _payload_digest(contract),
    }


def build_v0_loaded_context(
    replay_block: dict[str, Any],
    *,
    role: str,
    config_path: Path | None = None,
    role_focus: str | None = None,
) -> dict[str, str]:
    contract, contract_path = _contract(config_path)
    loader_policy = dict(contract.get("loader_policy") or {})
    role_focus_by_role = {
        str(key): str(value)
        for key, value in dict(loader_policy.get("role_focus_by_role") or {}).items()
    }
    if role not in role_focus_by_role:
        raise ValueError(f"V0 replay loader does not support role={role!r}.")

    replay_text = str(replay_block.get("artifact_body") or replay_block.get("content") or "").strip()
    if not replay_text:
        raise ValueError("V0 replay loader requires a non-empty replay block.")

    focus_text = str(role_focus or role_focus_by_role[role]).strip()
    if not focus_text:
        raise ValueError(f"V0 replay loader requires non-empty role focus for role={role}.")

    role_focus_header = str(loader_policy.get("role_focus_header") or "#### Role Focus").strip()
    text = f"{replay_text}\n{role_focus_header}\n- {focus_text}".strip()
    return {
        "text": text,
        "delivery_mode": str(loader_policy.get("delivery_mode") or "replay_block_verbatim_plus_role_focus"),
        "loader_contract_path": str(contract_path),
        "loader_contract_sha256": _payload_digest(contract),
        "replay_block_sha256": str(replay_block.get("artifact_sha256") or ""),
    }
