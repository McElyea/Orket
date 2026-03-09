from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render Companion provider/runtime matrix JSON into a markdown report.",
    )
    parser.add_argument(
        "--input",
        default="benchmarks/results/companion/provider_runtime_matrix/companion_provider_runtime_matrix.json",
        help="Path to matrix JSON artifact.",
    )
    parser.add_argument(
        "--output",
        default="benchmarks/results/companion/provider_runtime_matrix/README.md",
        help="Path for markdown report output.",
    )
    return parser


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("matrix artifact must be a JSON object")
    return payload


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_No rows._"
    divider = ["---" for _ in headers]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(divider) + " |",
    ]
    for row in rows:
        normalized = [str(cell or "") for cell in row]
        lines.append("| " + " | ".join(normalized) + " |")
    return "\n".join(lines)


def _recommendation_rows(payload: dict[str, Any]) -> list[list[str]]:
    by_rig_class = dict(((payload.get("recommendations") or {}).get("by_rig_class") or {}))
    rows: list[list[str]] = []
    for rig_class in sorted(by_rig_class.keys()):
        profile_rows = dict(by_rig_class.get(rig_class) or {})
        for usage_profile in sorted(profile_rows.keys()):
            rec = dict(profile_rows.get(usage_profile) or {})
            rows.append(
                [
                    str(rig_class),
                    str(usage_profile),
                    str(rec.get("status") or ""),
                    str(rec.get("provider") or ""),
                    str(rec.get("model") or ""),
                    str(rec.get("composite_score") or ""),
                    str(rec.get("profile_coverage") or ""),
                ]
            )
    return rows


def _blocker_rows(payload: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in list(payload.get("blockers") or []):
        blocker = dict(item or {})
        rows.append(
            [
                str(blocker.get("provider") or ""),
                str(blocker.get("model") or ""),
                str(blocker.get("step") or ""),
                str(blocker.get("observed_path") or ""),
                str(blocker.get("category") or ""),
                str(blocker.get("error") or ""),
            ]
        )
    return rows


def _score_value(scores: dict[str, Any], key: str) -> str:
    score = dict(scores.get(key) or {})
    status = str(score.get("status") or "")
    value = score.get("value")
    if status != "measured":
        return f"{status or 'not_measured'}"
    return f"{value}"


def _case_rows(payload: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in list(payload.get("cases") or []):
        case = dict(item or {})
        scores = dict(case.get("scores") or {})
        rows.append(
            [
                str(case.get("provider") or ""),
                str(case.get("model") or ""),
                str(case.get("result") or ""),
                str(case.get("observed_path") or ""),
                str(case.get("latency_ms") or ""),
                _score_value(scores, "reasoning"),
                _score_value(scores, "memory_usefulness"),
                _score_value(scores, "voice_suitability"),
                _score_value(scores, "stability"),
                _score_value(scores, "mode_adherence"),
            ]
        )
    return rows


def render_markdown_report(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary") or {})
    lines: list[str] = []
    lines.append("# Companion Provider/Runtime Matrix Report")
    lines.append("")
    lines.append(f"- Rendered at (UTC): `{_now_utc_iso()}`")
    lines.append(f"- Artifact generated at (UTC): `{payload.get('generated_at_utc', '')}`")
    lines.append(f"- Status: `{payload.get('status', '')}`")
    lines.append(f"- Observed result: `{payload.get('observed_result', '')}`")
    lines.append(f"- Requested cases: `{summary.get('requested_cases', 0)}`")
    lines.append(f"- Successful cases: `{summary.get('successful_cases', 0)}`")
    lines.append(f"- Failed cases: `{summary.get('failed_cases', 0)}`")
    lines.append(f"- Blockers: `{summary.get('blocker_count', 0)}`")
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    lines.append(
        _md_table(
            ["Rig Class", "Usage Profile", "Status", "Provider", "Model", "Composite", "Coverage"],
            _recommendation_rows(payload),
        )
    )
    lines.append("")

    lines.append("## Blockers")
    lines.append("")
    lines.append(
        _md_table(
            ["Provider", "Model", "Step", "Observed Path", "Category", "Error"],
            _blocker_rows(payload),
        )
    )
    lines.append("")

    lines.append("## Case Scores")
    lines.append("")
    lines.append(
        _md_table(
            [
                "Provider",
                "Model",
                "Result",
                "Observed Path",
                "Avg Latency ms",
                "Reasoning",
                "Memory",
                "Voice",
                "Stability",
                "Mode",
            ],
            _case_rows(payload),
        )
    )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    input_path = Path(str(args.input)).resolve()
    output_path = Path(str(args.output)).resolve()
    if not input_path.exists():
        raise SystemExit(f"E_COMPANION_MATRIX_REPORT_INPUT_MISSING: {input_path}")

    payload = _load_payload(input_path)
    report = render_markdown_report(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
