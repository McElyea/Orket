"""Summarize measured render receipts without upgrading payload hashes to render proof."""

from __future__ import annotations

from typing import Any


def render_evidence(strict_json: dict[str, Any], tool_call: dict[str, Any]) -> dict[str, Any]:
    cases = strict_json["case_results"] + tool_call["case_results"]
    samples = cases
    hashes = sorted({row.get("template_source_sha256") for row in samples if row.get("template_source_sha256")})
    verified = bool(cases) and all(row.get("render_verified") and row.get("template_hash") for row in cases)
    return {
        "method": "provider_native_preview_byte_exact" if verified else "message_payload_audited",
        "render_observability_classification": "rendered_prompt_audited" if verified else "message_payload_audited",
        "template_hash_alg": "sha256" if verified else "",
        "verified": verified and len(hashes) == 1,
        "verified_cases": sum(bool(row.get("render_verified")) for row in cases),
        "template_source_sha256": hashes[0] if len(hashes) == 1 else "",
        "server_builds": sorted({str(row["server_build"]) for row in samples if row.get("server_build")}),
    }
