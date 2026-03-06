from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider

try:
    from scripts.protocol.local_prompting_conformance_helpers import (
        anti_meta_flags,
        mock_content,
        prompt_for_case,
        validate_case,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from protocol.local_prompting_conformance_helpers import (  # type: ignore[no-redef]
        anti_meta_flags,
        mock_content,
        prompt_for_case,
        validate_case,
    )


async def run_cases(
    *,
    provider: str,
    model: str,
    profile_id: str,
    task_class: str,
    case_ids: list[str],
    threshold: float,
    lmstudio_session_mode: str,
    lmstudio_session_id: str,
    mock: bool,
) -> dict[str, Any]:
    provider_client = None if mock else LocalModelProvider(model=model, temperature=0.0, timeout=90)
    failures: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    render_hashes: list[str] = []
    telemetry_samples: list[dict[str, Any]] = []
    anti_meta_counts = {"markdown_fence": 0, "protocol_chatter": 0}
    for case_id in case_ids:
        if mock:
            content = mock_content(task_class, case_id)
            raw: dict[str, Any] = {
                "profile_id": profile_id,
                "task_class": task_class,
                "template_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "template_hash_alg": "sha256",
                "lmstudio_session_mode": lmstudio_session_mode,
                "lmstudio_session_id_present": bool(lmstudio_session_id),
            }
        else:
            assert provider_client is not None
            runtime_context: dict[str, Any] = {
                "protocol_governed_enabled": task_class in {"strict_json", "tool_call"},
                "local_prompt_task_class": task_class,
                "local_prompting_mode": "enforce",
                "lmstudio_session_mode": lmstudio_session_mode,
            }
            if lmstudio_session_mode in {"context", "fixed"}:
                runtime_context["session_id"] = lmstudio_session_id or f"lmstudio-conformance-{profile_id}"
                if lmstudio_session_mode == "fixed":
                    runtime_context["lmstudio_session_id"] = runtime_context["session_id"]
            response = await provider_client.complete(
                [{"role": "user", "content": prompt_for_case(task_class, case_id)}],
                runtime_context=runtime_context,
            )
            content = str(response.content or "")
            raw = dict(response.raw or {})
        passed, failure = validate_case(task_class, content, case_id)
        if not passed:
            failures[failure] = failures.get(failure, 0) + 1
        anti_meta = anti_meta_flags(content)
        if anti_meta["markdown_fence"]:
            anti_meta_counts["markdown_fence"] += 1
        if anti_meta["protocol_chatter"]:
            anti_meta_counts["protocol_chatter"] += 1
        rows.append(
            {
                "case_id": case_id,
                "passed": passed,
                "failure_family": failure or None,
                "response_chars": len(content),
                "anti_meta": anti_meta,
            }
        )
        render_hash = str(raw.get("template_hash") or "")
        if render_hash:
            render_hashes.append(render_hash)
        telemetry_samples.append(
            {
                "profile_id": str(raw.get("profile_id") or ""),
                "task_class": str(raw.get("task_class") or ""),
                "template_hash_alg": str(raw.get("template_hash_alg") or ""),
                "effective_stop_sequences": list(raw.get("effective_stop_sequences") or []),
                "sampling_bundle": dict(raw.get("sampling_bundle") or {}),
                "lmstudio_session_mode": str(raw.get("lmstudio_session_mode") or ""),
                "lmstudio_session_id_present": bool(raw.get("lmstudio_session_id_present", False)),
            }
        )
    pass_count = sum(1 for row in rows if row["passed"])
    total = len(rows)
    pass_rate = float(pass_count) / float(max(1, total))
    return {
        "schema_version": f"local_prompting_conformance.{task_class}.v1",
        "provider": provider,
        "model": model,
        "profile_id": profile_id,
        "task_class": task_class,
        "total_cases": total,
        "pass_cases": pass_count,
        "pass_rate": round(pass_rate, 6),
        "threshold": threshold,
        "strict_ok": pass_rate >= threshold,
        "failure_families": failures,
        "case_results": rows,
        "render_hash_samples": sorted(set(render_hashes))[:20],
        "telemetry_samples": telemetry_samples[:20],
        "anti_meta_counts": anti_meta_counts,
    }
