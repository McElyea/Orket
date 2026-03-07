from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.common.evidence_environment import DEFAULT_EVIDENCE_ENV_KEYS
    from scripts.common.evidence_environment import collect_environment_metadata
    from scripts.common.evidence_environment import utc_now_iso
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.evidence_environment import DEFAULT_EVIDENCE_ENV_KEYS
    from common.evidence_environment import collect_environment_metadata
    from common.evidence_environment import utc_now_iso
    from common.rerun_diff_ledger import write_payload_with_diff_ledger


DEFAULT_OUT_ROOT = Path("benchmarks/results/techdebt/td03052026")
DEFAULT_PHASE_ID = "phase0_baseline"
GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
P0_GATES = {"G1", "G2", "G3", "G4"}
GATE_STATES = {"green", "red", "waived"}
READINESS_PREREQUISITES = ("G1", "G2", "G3", "G4", "G5")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record TD03052026 Phase-0 baseline evidence and hardening dashboard state.",
    )
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT), help="Output root for TD03052026 evidence.")
    parser.add_argument("--phase-id", default=DEFAULT_PHASE_ID, help="Phase identifier under out-root.")
    parser.add_argument("--install-mode", default="editable_dev", help="Install mode label for environment metadata.")
    parser.add_argument("--canonical-source", default="pyproject", help="Canonical dependency source label.")
    parser.add_argument("--command", action="append", default=[], help="Executed baseline command (repeatable).")
    parser.add_argument("--import-smoke-status", choices=["pass", "fail"], required=True)
    parser.add_argument("--entrypoint-help-status", choices=["pass", "fail"], required=True)
    parser.add_argument("--api-app-construction-status", choices=["pass", "fail"], required=True)
    parser.add_argument("--env-key", action="append", default=[], help="Additional env keys to capture (repeatable).")
    parser.add_argument(
        "--gate-state",
        action="append",
        default=[],
        help="Optional gate override in form Gx=<green|red|waived>:<detail> (repeatable).",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when phase result is not PASS.")
    return parser


def _status_to_bool(status: str) -> bool:
    return str(status or "").strip().lower() == "pass"


def _collect_environment(*, install_mode: str, canonical_source: str, env_keys: list[str]) -> dict[str, Any]:
    return collect_environment_metadata(
        schema_version="td03052026.environment.v1",
        package_mode=str(install_mode or "").strip(),
        env_keys=env_keys,
        extra_fields={"canonical_dependency_source": str(canonical_source or "").strip()},
    )


def _write_commands(path: Path, commands: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [f"{index}. {command}" for index, command in enumerate(commands, start=1)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _assertion(*, assertion_id: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"id": assertion_id, "passed": bool(passed), "detail": str(detail)}


def _build_result(
    *,
    phase_id: str,
    canonical_source: str,
    commands: list[str],
    import_smoke_status: str,
    entrypoint_help_status: str,
    api_app_construction_status: str,
) -> dict[str, Any]:
    canonical_ok = bool(str(canonical_source or "").strip())
    commands_ok = len(commands) >= 4
    import_ok = _status_to_bool(import_smoke_status)
    help_ok = _status_to_bool(entrypoint_help_status)
    api_ok = _status_to_bool(api_app_construction_status)
    assertions = [
        _assertion(
            assertion_id="commands_recorded",
            passed=commands_ok,
            detail=f"commands_count={len(commands)}; minimum=4",
        ),
        _assertion(
            assertion_id="canonical_source_declared",
            passed=canonical_ok,
            detail=f"canonical_source={str(canonical_source or '').strip() or '<missing>'}",
        ),
        _assertion(
            assertion_id="import_smoke_passed",
            passed=import_ok,
            detail=f"import_smoke_status={import_smoke_status}",
        ),
        _assertion(
            assertion_id="entrypoint_help_passed",
            passed=help_ok,
            detail=f"entrypoint_help_status={entrypoint_help_status}",
        ),
        _assertion(
            assertion_id="api_app_construction_passed",
            passed=api_ok,
            detail=f"api_app_construction_status={api_app_construction_status}",
        ),
    ]
    all_passed = all(bool(item["passed"]) for item in assertions)
    return {
        "schema_version": "td03052026.phase_result.v1",
        "recorded_at_utc": utc_now_iso(),
        "phase_id": str(phase_id),
        "status": "PASS" if all_passed else "FAIL",
        "assertions": assertions,
    }


def _empty_gate_map() -> dict[str, dict[str, Any]]:
    return {
        gate_id: {
            "state": "red",
            "detail": "not yet verified",
            "evidence": [],
            "updated_at_utc": utc_now_iso(),
        }
        for gate_id in GATE_IDS
    }


def _normalize_gate_entry(raw: Any, *, gate_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"state": "red", "detail": "not yet verified", "evidence": [], "updated_at_utc": utc_now_iso()}
    state = str(raw.get("state") or "red").strip().lower()
    if state not in GATE_STATES:
        state = "red"
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), list) else []
    return {
        "state": state,
        "detail": str(raw.get("detail") or "not yet verified"),
        "evidence": [str(item) for item in evidence],
        "updated_at_utc": str(raw.get("updated_at_utc") or utc_now_iso()),
    }


def _load_existing_gates(path: Path) -> dict[str, dict[str, Any]]:
    base = _empty_gate_map()
    if not path.exists():
        return base
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return base
    raw_gates = payload.get("gates")
    if not isinstance(raw_gates, dict):
        return base
    for gate_id in GATE_IDS:
        base[gate_id] = _normalize_gate_entry(raw_gates.get(gate_id), gate_id=gate_id)
    return base


def _parse_gate_override(token: str) -> tuple[str, str, str]:
    raw = str(token or "").strip()
    if not raw or "=" not in raw:
        raise ValueError(f"invalid gate override '{token}'; expected Gx=<state>:<detail>")
    gate_id_raw, rhs = raw.split("=", 1)
    gate_id = gate_id_raw.strip().upper()
    if gate_id not in GATE_IDS:
        raise ValueError(f"unknown gate id '{gate_id}' in override '{token}'")
    if ":" in rhs:
        state_raw, detail_raw = rhs.split(":", 1)
        state = state_raw.strip().lower()
        detail = detail_raw.strip()
    else:
        state = rhs.strip().lower()
        detail = ""
    if state not in GATE_STATES:
        raise ValueError(f"invalid gate state '{state}' in override '{token}'")
    if state == "waived" and gate_id in P0_GATES:
        raise ValueError(f"waived state is not permitted for P0 gate '{gate_id}'")
    return gate_id, state, detail or "manual override"


def _resolve_g1_state(result_payload: dict[str, Any]) -> tuple[str, str]:
    assertions = result_payload.get("assertions") if isinstance(result_payload.get("assertions"), list) else []
    required_ids = {
        "commands_recorded",
        "canonical_source_declared",
        "import_smoke_passed",
        "entrypoint_help_passed",
        "api_app_construction_passed",
    }
    by_id: dict[str, bool] = {}
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        assertion_id = str(assertion.get("id") or "").strip()
        if not assertion_id:
            continue
        by_id[assertion_id] = bool(assertion.get("passed"))
    missing_or_failed = sorted(token for token in required_ids if not by_id.get(token, False))
    if missing_or_failed:
        return "red", f"G1 prerequisites failed: {', '.join(missing_or_failed)}"
    return "green", "install parity baseline smoke assertions passed"


def _upsert_gate(
    gate_map: dict[str, dict[str, Any]],
    *,
    gate_id: str,
    state: str,
    detail: str,
    evidence: list[str] | None = None,
) -> None:
    entry = gate_map.get(gate_id) or {"state": "red", "detail": "", "evidence": []}
    entry["state"] = state
    entry["detail"] = detail
    entry["updated_at_utc"] = utc_now_iso()
    if evidence is not None:
        entry["evidence"] = list(evidence)
    gate_map[gate_id] = entry


def _enforce_g7_prerequisites(gate_map: dict[str, dict[str, Any]]) -> None:
    prereq_green = all(str(gate_map[token].get("state") or "") == "green" for token in READINESS_PREREQUISITES)
    g7_state = str(gate_map["G7"].get("state") or "")
    if g7_state == "green" and not prereq_green:
        _upsert_gate(
            gate_map,
            gate_id="G7",
            state="red",
            detail="cannot be green until G1-G5 are green",
            evidence=gate_map["G7"].get("evidence") if isinstance(gate_map["G7"].get("evidence"), list) else [],
        )


def _to_forward_slashes(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _build_dashboard_payload(
    *,
    out_root: Path,
    phase_id: str,
    commands_path: Path,
    environment_path: Path,
    result_path: Path,
    existing_gates: dict[str, dict[str, Any]],
    gate_overrides: list[str],
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    gate_map = {gate_id: dict(existing_gates[gate_id]) for gate_id in GATE_IDS}
    g1_state, g1_detail = _resolve_g1_state(result_payload)
    _upsert_gate(
        gate_map,
        gate_id="G1",
        state=g1_state,
        detail=g1_detail,
        evidence=[_to_forward_slashes(result_path), _to_forward_slashes(environment_path), _to_forward_slashes(commands_path)],
    )
    for token in gate_overrides:
        gate_id, state, detail = _parse_gate_override(token)
        _upsert_gate(gate_map, gate_id=gate_id, state=state, detail=detail)
    _enforce_g7_prerequisites(gate_map)
    return {
        "schema_version": "td03052026.hardening_dashboard.v1",
        "updated_at_utc": utc_now_iso(),
        "phase_id": str(phase_id),
        "out_root": _to_forward_slashes(out_root),
        "latest_phase_result": _to_forward_slashes(result_path),
        "latest_environment": _to_forward_slashes(environment_path),
        "latest_commands": _to_forward_slashes(commands_path),
        "gates": gate_map,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out_root = Path(str(args.out_root)).resolve()
        phase_id = str(args.phase_id).strip() or DEFAULT_PHASE_ID
        commands = [str(item).strip() for item in list(args.command or []) if str(item).strip()]
        if not commands:
            raise ValueError("at least one --command is required")
        phase_root = out_root / phase_id
        commands_path = phase_root / "commands.txt"
        environment_path = phase_root / "environment.json"
        result_path = phase_root / "result.json"
        dashboard_path = out_root / "hardening_dashboard.json"

        env_keys = sorted(set(DEFAULT_EVIDENCE_ENV_KEYS) | {str(key).strip() for key in list(args.env_key or []) if str(key).strip()})
        _write_commands(commands_path, commands)

        environment_payload = _collect_environment(
            install_mode=str(args.install_mode),
            canonical_source=str(args.canonical_source),
            env_keys=env_keys,
        )
        write_payload_with_diff_ledger(environment_path, environment_payload)

        result_payload = _build_result(
            phase_id=phase_id,
            canonical_source=str(args.canonical_source),
            commands=commands,
            import_smoke_status=str(args.import_smoke_status),
            entrypoint_help_status=str(args.entrypoint_help_status),
            api_app_construction_status=str(args.api_app_construction_status),
        )
        write_payload_with_diff_ledger(result_path, result_payload)

        existing_gates = _load_existing_gates(dashboard_path)
        dashboard_payload = _build_dashboard_payload(
            out_root=out_root,
            phase_id=phase_id,
            commands_path=commands_path,
            environment_path=environment_path,
            result_path=result_path,
            existing_gates=existing_gates,
            gate_overrides=[str(token) for token in list(args.gate_state or [])],
            result_payload=result_payload,
        )
        write_payload_with_diff_ledger(dashboard_path, dashboard_payload)

        if bool(args.strict) and str(result_payload.get("status") or "") != "PASS":
            return 1
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
