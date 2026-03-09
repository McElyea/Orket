from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import httpx

from scripts.companion.companion_matrix_case_selection import expand_case_pairs
from scripts.companion.render_companion_provider_runtime_report import render_markdown_report
from scripts.companion.run_companion_provider_runtime_matrix import run_companion_provider_runtime_matrix
from scripts.companion.validate_companion_provider_runtime_matrix import _load_json_object, validate_matrix_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Companion matrix pipeline: generate JSON, validate schema, render markdown.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--providers", default="ollama,lmstudio")
    parser.add_argument("--models", default="")
    parser.add_argument("--provider-model-map", default="")
    parser.add_argument("--rig-classes", default="A,B,C,D")
    parser.add_argument("--usage-profiles", default="chat-first,memory-heavy,voice-heavy")
    parser.add_argument("--session-id", default="companion-matrix")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--stability-attempts", type=int, default=2)
    parser.add_argument(
        "--output",
        default="benchmarks/results/companion/provider_runtime_matrix/companion_provider_runtime_matrix.json",
    )
    parser.add_argument(
        "--report-output",
        default="benchmarks/results/companion/provider_runtime_matrix/README.md",
    )
    parser.add_argument(
        "--schema",
        default="docs/specs/companion-provider-runtime-matrix.schema.json",
    )
    parser.add_argument("--strict-schema", action="store_true")
    return parser


def _parse_csv_tokens(raw: str) -> list[str]:
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


def run_matrix_pipeline(
    *,
    base_url: str,
    api_key: str,
    providers: list[str],
    models: list[str],
    provider_model_map: str,
    rig_classes: list[str],
    usage_profiles: list[str],
    session_id: str,
    timeout_s: float,
    stability_attempts: int,
    output_path: Path,
    report_output_path: Path,
    schema_path: Path,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    case_pairs = expand_case_pairs(
        providers=providers,
        models=models,
        provider_model_map=provider_model_map,
    )
    payload = run_companion_provider_runtime_matrix(
        base_url=base_url,
        api_key=api_key,
        providers=providers,
        models=models,
        case_pairs=case_pairs,
        rig_classes=rig_classes,
        usage_profiles=usage_profiles,
        session_id=session_id,
        timeout_s=timeout_s,
        stability_attempts=stability_attempts,
        output_path=output_path,
        transport=transport,
    )

    schema = _load_json_object(schema_path.resolve())
    validation_errors = validate_matrix_payload(payload=payload, schema=schema)

    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    report_output_path.write_text(render_markdown_report(payload), encoding="utf-8")
    return {
        "payload": payload,
        "validation_errors": validation_errors,
        "report_output": str(report_output_path.resolve()),
        "schema": str(schema_path.resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    providers = _parse_csv_tokens(args.providers)
    if not providers:
        raise SystemExit("E_COMPANION_MATRIX_PROVIDERS_REQUIRED")
    models = _parse_csv_tokens(args.models)
    rig_classes = [token.upper() for token in _parse_csv_tokens(args.rig_classes)] or ["A", "B", "C", "D"]
    usage_profiles = _parse_csv_tokens(args.usage_profiles) or ["chat-first", "memory-heavy", "voice-heavy"]
    result = run_matrix_pipeline(
        base_url=str(args.base_url),
        api_key=str(args.api_key),
        providers=providers,
        models=models,
        provider_model_map=str(args.provider_model_map or ""),
        rig_classes=rig_classes,
        usage_profiles=usage_profiles,
        session_id=str(args.session_id),
        timeout_s=float(args.timeout_s),
        stability_attempts=max(1, int(args.stability_attempts)),
        output_path=Path(str(args.output)),
        report_output_path=Path(str(args.report_output)),
        schema_path=Path(str(args.schema)),
    )
    payload = dict(result.get("payload") or {})
    errors = list(result.get("validation_errors") or [])
    print(f"status={payload.get('status')} schema_errors={len(errors)} report={result.get('report_output')}")
    if bool(args.strict_schema) and errors:
        return 1
    return 0 if str(payload.get("status") or "") == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
