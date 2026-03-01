from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from orket.adapters.tools.families.base import BaseTools
from orket.reforger.compiler import run_compile_pipeline
from orket.reforger.routes import ROUTE_ID_TEXTMYSTERY_PERSONA_V0, TextMysteryPersonaRouteV0


class ReforgerTools(BaseTools):
    _ROUTE_ALIASES = {
        "textmystery_v1": ROUTE_ID_TEXTMYSTERY_PERSONA_V0,
        ROUTE_ID_TEXTMYSTERY_PERSONA_V0: ROUTE_ID_TEXTMYSTERY_PERSONA_V0,
    }

    def inspect(self, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        del context
        route_id_raw = str(args.get("route_id") or "").strip()
        mode_raw = str(args.get("mode") or "").strip()
        scenario_pack_raw = str(args.get("scenario_pack") or "").strip()
        input_dir = self._resolve_safe_path(str(args.get("input_dir") or ""), write=False)

        route_id = self._resolve_route_id(route_id_raw or None, input_dir)
        if route_id is None:
            return {
                "ok": False,
                "tool": "reforger_inspect",
                "version": "1",
                "code": "ROUTE_NOT_FOUND",
                "error": "No route resolved for input set.",
            }

        route = TextMysteryPersonaRouteV0()
        plan = route.inspect(input_dir)
        suite_ready: bool | None = None
        suite_requirements: List[str] = []
        if mode_raw:
            if mode_raw != "truth_only":
                return {
                    "ok": False,
                    "tool": "reforger_inspect",
                    "version": "1",
                    "code": "MODE_UNSUPPORTED",
                    "error": f"Unsupported mode '{mode_raw}'",
                }
            suite_ready = bool(plan.ok)
            scenario_path = self._resolve_scenario_pack_path(scenario_pack_raw or None, input_dir)
            if scenario_path is None or not scenario_path.is_file():
                suite_ready = False
                suite_requirements.append("scenario_pack")

        artifact_root = self._artifact_root("inspect", route_id, input_dir, mode_raw or "none", 0, 0)
        artifact_root.mkdir(parents=True, exist_ok=True)

        route_plan_payload = {
            "version": "route_plan_v0",
            "route_id": route_id,
            "expected_inputs": list(plan.expected_inputs),
            "found_inputs": list(plan.found_inputs),
            "missing_inputs": list(plan.missing_inputs),
            "errors": list(plan.errors),
            "warnings": list(plan.warnings),
            "runnable": bool(plan.ok),
            "suite_ready": suite_ready,
            "suite_requirements": sorted(suite_requirements),
        }
        validation_payload = {
            "version": "validation_v0",
            "issues": self._issues_from_plan(plan),
        }
        (artifact_root / "route_plan.json").write_text(json.dumps(route_plan_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (
            artifact_root / "validation_report.normalize.json"
        ).write_text(json.dumps(validation_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "ok": bool(plan.ok),
            "tool": "reforger_inspect",
            "version": "1",
            "route_id": route_id,
            "runnable": bool(plan.ok),
            "suite_ready": suite_ready,
            "suite_requirements": sorted(suite_requirements),
            "missing_inputs": list(plan.missing_inputs),
            "errors": list(plan.errors),
            "warnings": list(plan.warnings),
            "artifact_root": str(artifact_root),
        }

    def run(self, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        del context
        route_id_raw = str(args.get("route_id") or "").strip()
        mode_raw = str(args.get("mode") or "").strip()
        scenario_pack_raw = str(args.get("scenario_pack") or "").strip()
        forced = bool(args.get("forced", False))
        force_reason = str(args.get("force_reason") or "")
        seed = int(args.get("seed", 0))
        max_iters = int(args.get("max_iters", 10))
        model_id = str(args.get("model_id") or "fake")
        input_dir = self._resolve_safe_path(str(args.get("input_dir") or ""), write=False)
        output_raw = str(args.get("output_dir") or "").strip()
        try:
            output_dir = self._validate_output_dir(output_raw)
        except ValueError as exc:
            return {
                "ok": False,
                "tool": "reforger_run",
                "version": "1",
                "code": "PATCH_OUT_OF_SURFACE",
                "error": str(exc),
            }

        route_id = self._resolve_route_id(route_id_raw or None, input_dir)
        if route_id is None:
            return {
                "ok": False,
                "tool": "reforger_run",
                "version": "1",
                "code": "ROUTE_NOT_FOUND",
                "error": "No route resolved for input set.",
            }
        if mode_raw != "truth_only":
            return {
                "ok": False,
                "tool": "reforger_run",
                "version": "1",
                "code": "MODE_UNSUPPORTED",
                "error": f"Unsupported mode '{mode_raw}'",
            }
        artifact_root = self._artifact_root("run", route_id, input_dir, mode_raw, seed, max_iters)
        scenario_pack_path = self._resolve_scenario_pack_path(scenario_pack_raw or None, input_dir)
        warnings: List[str] = []
        if scenario_pack_path is None or not scenario_pack_path.is_file():
            if not forced:
                return {
                    "ok": False,
                    "tool": "reforger_run",
                    "version": "1",
                    "code": "SUITE_NOT_READY",
                    "error": "Scenario pack not found.",
                }
            scenario_pack_path = self._write_forced_fallback_scenario_pack(artifact_root, mode_raw)
            warnings.append("forced_without_scenario_pack")

        run_out_dir = artifact_root / "run"
        result = run_compile_pipeline(
            route_id=route_id,
            input_dir=input_dir,
            out_dir=run_out_dir,
            mode=mode_raw,
            model_id=model_id,
            seed=seed,
            max_iters=max_iters,
            scenario_pack_path=scenario_pack_path,
        )
        materialized_src = result.materialized_root
        if output_dir.exists():
            for child in output_dir.iterdir():
                if child.is_file():
                    child.unlink()
                else:
                    import shutil

                    shutil.rmtree(child)
        output_dir.mkdir(parents=True, exist_ok=True)
        for item in materialized_src.rglob("*"):
            rel = item.relative_to(materialized_src)
            dest = output_dir / rel
            if item.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(item.read_bytes())

        return {
            "ok": bool(result.ok),
            "tool": "reforger_run",
            "version": "1",
            "route_id": route_id,
            "hard_fail_count": int(result.hard_fail_count),
            "best_score": float(result.best_score),
            "best_candidate_id": str(result.best_candidate_id),
            "artifact_root": str(artifact_root),
            "materialized_output_dir": str(output_dir),
            "forced": forced,
            "force_reason": force_reason,
            "warnings": warnings,
        }

    def _resolve_route_id(self, route_id: str | None, input_dir: Path) -> str | None:
        if route_id:
            normalized = self._ROUTE_ALIASES.get(route_id.strip().lower())
            return normalized
        candidate = TextMysteryPersonaRouteV0()
        plan = candidate.inspect(input_dir)
        return candidate.route_id if plan.ok else None

    def _resolve_scenario_pack_path(self, scenario_pack: str | None, input_dir: Path) -> Path | None:
        if not scenario_pack:
            return input_dir / "reforge" / "scenario_packs" / "truth_only_v0.json"
        raw = str(scenario_pack).strip()
        direct = Path(raw)
        if direct.suffix.lower() == ".json":
            if direct.is_absolute():
                return direct
            return (input_dir / raw).resolve()
        return (input_dir / "reforge" / "scenario_packs" / f"{raw}.json").resolve()

    def _artifact_root(
        self,
        kind: str,
        route_id: str,
        input_dir: Path,
        mode: str,
        seed: int,
        max_iters: int,
    ) -> Path:
        payload = {
            "kind": kind,
            "route_id": route_id,
            "input_dir": str(input_dir).replace("\\", "/").lower(),
            "mode": mode,
            "seed": seed,
            "max_iters": max_iters,
        }
        key = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        run_id = hashlib.sha256(key).hexdigest()[:16]
        return self.workspace_root / "reforger" / kind / run_id

    def _issues_from_plan(self, plan: Any) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        for rel in sorted(plan.missing_inputs):
            issues.append(
                {
                    "code": "INPUT_MISSING",
                    "severity": "error",
                    "path": rel,
                    "message": f"Required input missing: {rel}",
                }
            )
        for msg in sorted(plan.errors):
            code = "SCHEMA_INVALID"
            if "unknown archetype" in msg.lower() or "unknown refusal_style" in msg.lower():
                code = "REF_INVALID"
            issues.append({"code": code, "severity": "error", "path": "", "message": msg})
        for msg in sorted(plan.warnings):
            issues.append({"code": "INTERNAL_ERROR", "severity": "warning", "path": "", "message": msg})
        return issues

    def _validate_output_dir(self, output_raw: str) -> Path:
        if not output_raw:
            raise ValueError("output_dir is required")
        candidate = Path(output_raw)
        if candidate.is_absolute():
            raise ValueError("output_dir must be workspace-relative, not absolute")
        if ".." in candidate.parts:
            raise ValueError("output_dir must not contain '..'")
        resolved = self._resolve_safe_path(output_raw, write=True)
        return resolved

    def _write_forced_fallback_scenario_pack(self, artifact_root: Path, mode: str) -> Path:
        payload = {
            "pack_id": "forced_truth_only_fallback_v0",
            "version": "1.0.0",
            "mode": mode,
            "tests": [
                {"id": "TRUTH_001", "kind": "npc_archetype_exists", "hard": True, "weight": 1.0},
                {"id": "TRUTH_002", "kind": "npc_refusal_style_exists", "hard": True, "weight": 1.0},
            ],
        }
        path = artifact_root / "forced_scenario_pack.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path
