#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.adapters.llm.local_model_provider import LocalModelProvider
from scripts.probes.probe_support import applied_probe_env, is_environment_blocker, json_safe, now_utc_iso, write_report
from scripts.reviewrun.score_answer_key import score_answer_key
from scripts.workloads.code_review_probe_support import (
    DEFAULT_PROMPT_PROFILE,
    DEFAULT_REVIEW_METHOD,
    artifact_inventory,
    build_deterministic_payload,
    build_guard_messages,
    build_review_messages,
    build_snapshot_payload,
    display_path,
    load_json_object,
    load_text,
    prompt_profile_names,
    sha256_text,
    usage_payload,
    usage_responses,
    validated_review_payload,
    write_json,
)

DEFAULT_OUTPUT = "benchmarks/results/workloads/code_review_probe.json"
DEFAULT_FIXTURE = "scripts/workloads/fixtures/code_review_probe_v1/corrupt_order_processor.py"
DEFAULT_ANSWER_KEY = "scripts/workloads/fixtures/code_review_probe_v1/human_review_answer_key.json"
DEFAULT_WORKSPACE = "workspace/default"
_REVIEW_METHODS = ("single_pass", "self_check")
_usage_payload = usage_payload
_usage_responses = usage_responses


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3 workload S-04: standalone live code review probe.")
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--ollama-host", default="")
    parser.add_argument("--fixture", default=DEFAULT_FIXTURE)
    parser.add_argument("--answer-key", default=DEFAULT_ANSWER_KEY)
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--prompt-profile", default=DEFAULT_PROMPT_PROFILE, choices=prompt_profile_names())
    parser.add_argument("--review-method", default=DEFAULT_REVIEW_METHOD, choices=_REVIEW_METHODS)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _run_id() -> str:
    return f"s04-{secrets.token_hex(8)}"


async def _complete_review(
    provider: LocalModelProvider,
    *,
    messages: list[dict[str, str]],
    answer_key: dict[str, Any],
    args: argparse.Namespace,
    review_pass: str,
) -> Any:
    return await provider.complete(
        messages,
        runtime_context={
            "workload_id": "S-04",
            "fixture_id": str(answer_key.get("fixture_id") or ""),
            "local_prompt_task_class": "strict_json",
            "prompt_profile": str(args.prompt_profile),
            "review_method": str(args.review_method),
            "review_pass": review_pass,
        },
    )


def _build_model_assisted_payload(
    *,
    review_payload: dict[str, Any],
    run_id: str,
    model: str,
    source_text: str,
    prompt_profile: str,
    review_method: str,
) -> dict[str, Any]:
    return {
        **review_payload,
        "model_id": str(model),
        "prompt_profile": str(prompt_profile),
        "review_method": str(review_method),
        "contract_version": "review_critique_v0",
        "snapshot_digest": sha256_text(source_text),
        "policy_digest": sha256_text("workloads.s04_code_review_probe.v2"),
        "run_id": str(run_id),
    }


def _score_review_bundle(*, artifact_dir: Path, answer_key_path: Path) -> dict[str, Any]:
    score = score_answer_key(run_dir=artifact_dir, answer_key_path=answer_key_path)
    score["model_missed_must_catch"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("must_catch")) and not bool(row.get("model_hit"))
    ]
    score["model_hit_issue_ids"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("model_hit"))
    ]
    score["deterministic_missed_must_catch"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("must_catch")) and not bool(row.get("deterministic_hit"))
    ]
    score["deterministic_hit_issue_ids"] = [
        str(row.get("issue_id") or "")
        for row in list(score.get("issues") or [])
        if bool(row.get("present")) and bool(row.get("deterministic_hit"))
    ]
    return score


def _quality_summary(score: dict[str, Any], *, contract_valid: bool) -> dict[str, Any]:
    model = score.get("model_assisted") if isinstance(score.get("model_assisted"), dict) else {}
    deterministic = score.get("deterministic") if isinstance(score.get("deterministic"), dict) else {}
    missed = [str(item) for item in list(score.get("model_missed_must_catch") or []) if str(item).strip()]
    coverage = float(model.get("coverage") or 0.0)
    if not contract_valid:
        verdict = "contract_invalid"
    elif missed:
        verdict = "missed_must_catch"
    elif coverage > 0.0:
        verdict = "all_must_catch_caught"
    else:
        verdict = "no_useful_hits"
    return {
        "quality_verdict": verdict,
        "model_coverage": coverage,
        "model_score": int(model.get("score") or 0),
        "model_max_score": int(model.get("max_score") or 0),
        "model_reasoning_score": int(model.get("reasoning_score") or 0),
        "model_reasoning_max_score": int(model.get("reasoning_max_score") or 0),
        "model_fix_score": int(model.get("fix_score") or 0),
        "model_fix_max_score": int(model.get("fix_max_score") or 0),
        "model_missed_must_catch": missed,
        "model_hit_issue_ids": [str(item) for item in list(score.get("model_hit_issue_ids") or []) if str(item).strip()],
        "deterministic_coverage": float(deterministic.get("coverage") or 0.0),
        "deterministic_score": int(deterministic.get("score") or 0),
        "deterministic_max_score": int(deterministic.get("max_score") or 0),
        "deterministic_missed_must_catch": [
            str(item) for item in list(score.get("deterministic_missed_must_catch") or []) if str(item).strip()
        ],
        "deterministic_hit_issue_ids": [
            str(item) for item in list(score.get("deterministic_hit_issue_ids") or []) if str(item).strip()
        ],
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text), encoding="utf-8")


def _write_artifacts(
    *,
    artifact_dir: Path,
    fixture_path: Path,
    answer_key_path: Path,
    source_text: str,
    initial_messages: list[dict[str, str]],
    initial_response_text: str,
    initial_response_raw: dict[str, Any],
    initial_review: dict[str, Any],
    final_response_text: str,
    final_response_raw: dict[str, Any],
    final_review: dict[str, Any],
    guard_messages: list[dict[str, str]] | None,
    deterministic_payload: dict[str, Any],
    run_id: str,
    model: str,
    prompt_profile: str,
    review_method: str,
) -> dict[str, Any]:
    critique_payload = _build_model_assisted_payload(
        review_payload=final_review,
        run_id=run_id,
        model=model,
        source_text=source_text,
        prompt_profile=prompt_profile,
        review_method=review_method,
    )
    write_json(
        artifact_dir / "request.json",
        {
            "run_id": run_id,
            "fixture_path": fixture_path.as_posix(),
            "model": model,
            "prompt_profile": prompt_profile,
            "review_method": review_method,
        },
    )
    write_json(artifact_dir / "messages.json", initial_messages)
    if guard_messages is not None:
        write_json(artifact_dir / "guard_messages.json", guard_messages)
    write_json(artifact_dir / "snapshot.json", build_snapshot_payload(fixture_path=fixture_path, source_text=source_text))
    write_json(artifact_dir / "deterministic_decision.json", deterministic_payload)
    write_json(artifact_dir / "model_assisted_critique.json", critique_payload)
    write_json(artifact_dir / "parsed_review.json", critique_payload)
    write_json(artifact_dir / "model_response_raw.json", final_response_raw)
    write_json(artifact_dir / "response_metadata.json", {"response_sha256": sha256_text(final_response_text)})
    _write_text(artifact_dir / "model_response.txt", final_response_text)
    _write_text(artifact_dir / "fixture_source.py", source_text)
    _write_text(artifact_dir / "human_review_answer_key.json", load_text(answer_key_path))
    if review_method == "self_check":
        write_json(artifact_dir / "draft_review.json", initial_review)
        write_json(artifact_dir / "draft_model_response_raw.json", initial_response_raw)
        _write_text(artifact_dir / "draft_model_response.txt", initial_response_text)
    score = _score_review_bundle(artifact_dir=artifact_dir, answer_key_path=answer_key_path)
    write_json(artifact_dir / "score.json", score)
    return score


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    fixture_path = Path(str(args.fixture)).resolve()
    answer_key_path = Path(str(args.answer_key)).resolve()
    workspace = Path(str(args.workspace)).resolve()
    if not fixture_path.is_file():
        raise FileNotFoundError(f"fixture_not_found:{fixture_path}")
    if not answer_key_path.is_file():
        raise FileNotFoundError(f"answer_key_not_found:{answer_key_path}")

    source_text = load_text(fixture_path)
    answer_key = load_json_object(answer_key_path)
    fixture_display_path = Path(display_path(fixture_path))
    initial_messages = build_review_messages(
        fixture_path=fixture_display_path,
        source_text=source_text,
        prompt_profile=str(args.prompt_profile),
    )
    deterministic_payload = build_deterministic_payload(source_text=source_text, answer_key=answer_key)
    run_id = _run_id()
    artifact_dir = workspace / "workloads" / "s04_code_review_probe" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    guard_messages: list[dict[str, str]] | None = None
    final_response = None
    final_review: dict[str, Any] = {}
    initial_review: dict[str, Any] = {}
    initial_response = None

    with applied_probe_env(
        provider=str(args.provider),
        ollama_host=str(args.ollama_host or "").strip() or None,
        disable_sandbox=True,
    ):
        provider = LocalModelProvider(
            model=str(args.model),
            temperature=float(args.temperature),
            seed=int(args.seed),
            timeout=int(args.timeout),
        )
        try:
            initial_response = await _complete_review(
                provider,
                messages=initial_messages,
                answer_key=answer_key,
                args=args,
                review_pass="initial",
            )
            initial_review, _, _, _ = validated_review_payload(str(initial_response.content or ""))
            final_response = initial_response
            final_review = initial_review
            if str(args.review_method) == "self_check":
                guard_messages = build_guard_messages(
                    fixture_path=fixture_display_path,
                    source_text=source_text,
                    draft_response_text=str(initial_response.content or ""),
                    prompt_profile=str(args.prompt_profile),
                )
                final_response = await _complete_review(
                    provider,
                    messages=guard_messages,
                    answer_key=answer_key,
                    args=args,
                    review_pass="guard",
                )
                final_review, _, _, _ = validated_review_payload(str(final_response.content or ""))
        finally:
            await provider.close()

    parsed_review, response_json_found, contract_valid, advisory_errors = validated_review_payload(str(final_response.content or ""))
    score = _write_artifacts(
        artifact_dir=artifact_dir,
        fixture_path=fixture_display_path,
        answer_key_path=answer_key_path,
        source_text=source_text,
        initial_messages=initial_messages,
        initial_response_text=str(initial_response.content or ""),
        initial_response_raw=json_safe(dict(initial_response.raw or {})),
        initial_review=initial_review,
        final_response_text=str(final_response.content or ""),
        final_response_raw=json_safe(dict(final_response.raw or {})),
        final_review=parsed_review,
        guard_messages=guard_messages,
        deterministic_payload=deterministic_payload,
        run_id=run_id,
        model=str(args.model),
        prompt_profile=str(args.prompt_profile),
        review_method=str(args.review_method),
    )
    quality = _quality_summary(score, contract_valid=contract_valid)
    observed_result = "partial success" if advisory_errors else "success"
    return {
        "schema_version": "workloads.s04_code_review_probe.v2",
        "recorded_at_utc": now_utc_iso(),
        "workload_id": "S-04",
        "probe_status": "observed",
        "proof_kind": "live",
        "observed_path": "primary",
        "observed_result": observed_result,
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "prompt_profile": str(args.prompt_profile),
        "review_method": str(args.review_method),
        "fixture": {
            "fixture_id": str(answer_key.get("fixture_id") or ""),
            "source_path": display_path(fixture_path),
            "answer_key_path": display_path(answer_key_path),
            "source_sha256": sha256_text(source_text),
            "source_lines": len(source_text.splitlines()),
        },
        "artifact_bundle": {
            "run_id": run_id,
            "artifact_dir": artifact_dir.as_posix(),
            "files": artifact_inventory(artifact_dir),
        },
        "review_contract": {
            "contract_version": "review_critique_v0",
            "response_json_found": response_json_found,
            "contract_valid": contract_valid,
            "advisory_errors": advisory_errors,
            "high_risk_issue_count": len(list(parsed_review.get("high_risk_issues") or [])),
        },
        "score": quality,
        "score_report": score,
        "deterministic_lane": {
            "version": str(deterministic_payload.get("deterministic_lane_version") or ""),
            "finding_count": len(list(deterministic_payload.get("findings") or [])),
            "executed_check_count": len(list(deterministic_payload.get("executed_checks") or [])),
        },
        "provider_usage": usage_payload(
            usage_responses(
                initial_response=initial_response,
                final_response=final_response,
                review_method=str(args.review_method),
            )
        ),
    }


def _blocked_payload(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    blocked = is_environment_blocker(error)
    return {
        "schema_version": "workloads.s04_code_review_probe.v2",
        "recorded_at_utc": now_utc_iso(),
        "workload_id": "S-04",
        "probe_status": "blocked",
        "proof_kind": "live",
        "observed_path": "blocked" if blocked else "primary",
        "observed_result": "environment blocker" if blocked else "failure",
        "requested_provider": str(args.provider),
        "requested_model": str(args.model),
        "prompt_profile": str(args.prompt_profile),
        "review_method": str(args.review_method),
        "fixture": {
            "source_path": str(args.fixture),
            "answer_key_path": str(args.answer_key),
        },
        "error_type": type(error).__name__,
        "error": str(error),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(str(args.output)).resolve()
    try:
        payload = asyncio.run(_run_probe(args))
    except Exception as exc:  # noqa: BLE001
        payload = _blocked_payload(args, exc)

    persisted = write_report(output_path, payload)
    if args.json:
        print(json.dumps({**persisted, "output_path": str(output_path)}, indent=2, ensure_ascii=True))
    else:
        quality = persisted.get("score") if isinstance(persisted.get("score"), dict) else {}
        print(
            " ".join(
                [
                    f"probe_status={persisted.get('probe_status')}",
                    f"observed_result={persisted.get('observed_result')}",
                    f"quality_verdict={quality.get('quality_verdict', '')}",
                    f"output={output_path}",
                ]
            )
        )
    return 0 if str(persisted.get("probe_status") or "") == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
