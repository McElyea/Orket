from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return payload


def evaluate_enforcement_flip_gate(
    *,
    ci_failure_payload: dict[str, Any],
    compat_warnings_payload: dict[str, Any],
    compat_expiry_payload: dict[str, Any],
    security_regression_payload: dict[str, Any],
) -> dict[str, Any]:
    p0_open = int(((ci_failure_payload.get("summary") or {}).get("p0")) or 0)
    compat_warning_count = int(compat_warnings_payload.get("warning_count") or 0)
    compat_expiry_ok = bool(compat_expiry_payload.get("ok", False))
    security_regression_ok = bool(security_regression_payload.get("ok", False))

    checks = {
        "p0_open_zero": p0_open == 0,
        "security_regressions_green": security_regression_ok,
        "compat_warning_count_zero": compat_warning_count == 0,
        "compat_expiry_green": compat_expiry_ok,
    }
    failures: list[str] = []
    if not checks["p0_open_zero"]:
        failures.append(f"p0_open={p0_open} (expected 0)")
    if not checks["security_regressions_green"]:
        failures.append("security regressions not green")
    if not checks["compat_warning_count_zero"]:
        failures.append(f"compat warnings present: {compat_warning_count}")
    if not checks["compat_expiry_green"]:
        failures.append("compat expiry check not green")

    return {
        "ok": len(failures) == 0,
        "checks": checks,
        "summary": {
            "p0_open": p0_open,
            "compat_warning_count": compat_warning_count,
            "compat_expiry_ok": compat_expiry_ok,
            "security_regression_ok": security_regression_ok,
        },
        "failures": failures,
    }


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Security Enforcement Flip Gate",
        "",
        f"- ok: `{str(result['ok']).lower()}`",
        f"- p0_open: `{result['summary']['p0_open']}`",
        f"- compat_warning_count: `{result['summary']['compat_warning_count']}`",
        f"- compat_expiry_ok: `{str(result['summary']['compat_expiry_ok']).lower()}`",
        f"- security_regression_ok: `{str(result['summary']['security_regression_ok']).lower()}`",
        "",
        "## Failures",
    ]
    failures = list(result.get("failures", []))
    if failures:
        for item in failures:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate security enforcement flip gates.")
    parser.add_argument("--ci-failure-json", default="benchmarks/results/ci_failure_dump.json")
    parser.add_argument("--compat-warnings-json", default="benchmarks/results/security_compat_warnings.json")
    parser.add_argument("--compat-expiry-json", default="benchmarks/results/security_compat_expiry_check.json")
    parser.add_argument("--security-regression-json", default="benchmarks/results/security_regression_status.json")
    parser.add_argument("--out-json", default="benchmarks/results/security_enforcement_flip_gate.json")
    parser.add_argument("--out-md", default="benchmarks/results/security_enforcement_flip_gate.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = evaluate_enforcement_flip_gate(
        ci_failure_payload=_load_json(Path(args.ci_failure_json)),
        compat_warnings_payload=_load_json(Path(args.compat_warnings_json)),
        compat_expiry_payload=_load_json(Path(args.compat_expiry_json)),
        security_regression_payload=_load_json(Path(args.security_regression_json)),
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())

