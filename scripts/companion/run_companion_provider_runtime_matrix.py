from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scripts.companion.companion_matrix_execution import coverage_blockers, evaluate_case
from scripts.companion.companion_matrix_scoring import RIG_CLASSES, USAGE_PROFILES, build_recommendation_matrix
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_csv_tokens(raw: str) -> list[str]:
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


def run_companion_provider_runtime_matrix(
    *,
    base_url: str,
    api_key: str,
    providers: list[str],
    models: list[str],
    rig_classes: list[str],
    usage_profiles: list[str],
    session_id: str,
    timeout_s: float,
    stability_attempts: int,
    output_path: Path,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    timeout = max(1.0, float(timeout_s))

    cases: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport) as client:
        for index, provider in enumerate(providers):
            model = models[index] if index < len(models) else ""
            case_payload, case_blockers = evaluate_case(
                client=client,
                session_id=f"{session_id}-{provider}-{index + 1}",
                provider=provider,
                model=model,
                stability_attempts=stability_attempts,
            )
            cases.append(case_payload)
            blockers.extend(case_blockers)

    blockers.extend(coverage_blockers(cases))
    recommendations = build_recommendation_matrix(
        cases=cases,
        rig_classes=rig_classes,
        usage_profiles=usage_profiles,
    )

    case_failures = [row for row in cases if row.get("result") != "success"]
    status = "complete" if not case_failures and not blockers else "partial"
    success_count = sum(1 for row in cases if row.get("result") == "success")
    if status == "complete":
        observed_result = "success"
    elif success_count > 0:
        observed_result = "partial success"
    else:
        observed_result = "failure"

    payload = {
        "generated_at_utc": _now_utc_iso(),
        "status": status,
        "observed_result": observed_result,
        "providers_requested": providers,
        "models_requested": models,
        "rig_classes_requested": rig_classes,
        "usage_profiles_requested": usage_profiles,
        "cases": cases,
        "recommendations": recommendations,
        "blockers": blockers,
        "summary": {
            "requested_cases": len(providers),
            "successful_cases": success_count,
            "failed_cases": len(case_failures),
            "blocker_count": len(blockers),
        },
    }
    return write_payload_with_diff_ledger(output_path, payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Companion provider/runtime matrix checks through public host API seams.",
    )
    parser.add_argument("--base-url", default=os.getenv("COMPANION_HOST_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("ORKET_API_KEY", ""))
    parser.add_argument("--providers", default="ollama,lmstudio")
    parser.add_argument("--models", default="")
    parser.add_argument("--rig-classes", default="A,B,C,D")
    parser.add_argument("--usage-profiles", default="chat-first,memory-heavy,voice-heavy")
    parser.add_argument("--session-id", default="companion-matrix")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--stability-attempts", type=int, default=2)
    parser.add_argument(
        "--output",
        default="benchmarks/results/companion/provider_runtime_matrix/companion_provider_runtime_matrix.json",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def _validated_or_default(tokens: list[str], defaults: tuple[str, ...], *, label: str) -> list[str]:
    if not tokens:
        return list(defaults)
    allowed = {token for token in defaults}
    invalid = [token for token in tokens if token not in allowed]
    if invalid:
        raise SystemExit(f"E_COMPANION_MATRIX_INVALID_{label.upper()}: {','.join(invalid)}")
    return tokens


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    providers = _parse_csv_tokens(args.providers)
    if not providers:
        raise SystemExit("E_COMPANION_MATRIX_PROVIDERS_REQUIRED")
    models = _parse_csv_tokens(args.models)
    rig_classes = _validated_or_default(
        [token.upper() for token in _parse_csv_tokens(args.rig_classes)],
        RIG_CLASSES,
        label="rig_classes",
    )
    usage_profiles = _validated_or_default(
        _parse_csv_tokens(args.usage_profiles),
        USAGE_PROFILES,
        label="usage_profiles",
    )

    payload = run_companion_provider_runtime_matrix(
        base_url=str(args.base_url),
        api_key=str(args.api_key),
        providers=providers,
        models=models,
        rig_classes=rig_classes,
        usage_profiles=usage_profiles,
        session_id=str(args.session_id),
        timeout_s=float(args.timeout_s),
        stability_attempts=max(1, int(args.stability_attempts)),
        output_path=Path(args.output),
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"status={payload.get('status')} output={args.output}")
    return 0 if str(payload.get("status") or "") == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
