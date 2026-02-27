from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.core.contracts import WORKLOAD_CONTRACT_VERSION_V1, parse_workload_contract


ERROR_PREFLIGHT = "E_ARB_PREFLIGHT_MISSING_MATERIAL"
ERROR_EXECUTION = "E_ARB_EXECUTION_FAILED"
ERROR_SHAPE = "E_ARB_VALIDATOR_SHAPE"
ERROR_LEAK = "E_ARB_VALIDATOR_LEAK"
ERROR_TRACE = "E_ARB_VALIDATOR_TRACE"
ERROR_POSTFLIGHT = "E_ARB_POSTFLIGHT_MISSING_ARTIFACT"


class ArbiterFailure(RuntimeError):
    def __init__(
        self,
        *,
        phase: str,
        code: str,
        message: str,
        failures: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.code = code
        self.message = message
        self.failures = sorted(failures or [])
        self.context = context or {}


@dataclass(frozen=True)
class PlanMaterial:
    kind: str
    value: str
    required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "required": self.required,
        }


class RunArbiter:
    def __init__(self, *, plan_out: Path, error_out: Path) -> None:
        self.plan_out = plan_out
        self.error_out = error_out

    def compile_plan(
        self,
        *,
        python_bin: str,
        base_spec: Path,
        out_dir: Path,
        index_out: Path,
        provenance_out: Path | None,
        require_provenance: bool,
        require_clean_git: bool,
        architects: list[str],
        auditors: list[str],
    ) -> dict[str, Any]:
        run_pairs = [
            {
                "architect_model": architect,
                "auditor_model": auditor,
                "artifact": str(
                    (out_dir / f"odr_live_role_matrix.{self._slug(architect)}_{self._slug(auditor)}.json").as_posix()
                ),
            }
            for architect in architects
            for auditor in auditors
        ]
        materials: list[PlanMaterial] = [
            PlanMaterial(kind="tool", value=python_bin),
            PlanMaterial(kind="tool", value="ollama"),
            PlanMaterial(kind="file", value=str(base_spec.as_posix())),
            PlanMaterial(kind="file", value="scripts/run_odr_live_role_matrix.py"),
            PlanMaterial(kind="file", value="scripts/generate_odr_role_matrix_index.py"),
        ]
        if require_provenance:
            materials.append(PlanMaterial(kind="file", value="scripts/generate_odr_provenance.py"))
        if require_clean_git:
            materials.append(PlanMaterial(kind="git", value="clean_worktree"))
        for model_id in sorted({*architects, *auditors}):
            materials.append(PlanMaterial(kind="model", value=model_id))

        expected_artifacts = [row["artifact"] for row in run_pairs]
        expected_artifacts.append(str(index_out.as_posix()))
        if require_provenance and provenance_out is not None:
            expected_artifacts.append(str(provenance_out.as_posix()))
        summary_targets = [str(index_out.as_posix())]
        provenance_targets = [str(provenance_out.as_posix())] if require_provenance and provenance_out is not None else []
        workload_contract = parse_workload_contract(
            {
                "workload_contract_version": WORKLOAD_CONTRACT_VERSION_V1,
                "workload_type": "odr",
                "units": list(run_pairs),
                "required_materials": [item.as_dict() for item in materials],
                "expected_artifacts": sorted(expected_artifacts),
                "validators": ["shape", "leak", "trace"],
                "summary_targets": summary_targets,
                "provenance_targets": provenance_targets,
            }
        ).model_dump()

        return {
            "schema_version": "odr.run_arbiter.plan.v1",
            "runner": "run_odr_quant_sweep.py",
            "required_materials": [item.as_dict() for item in materials],
            "run_pairs": run_pairs,
            "expected_artifacts": sorted(expected_artifacts),
            "workload_contract": workload_contract,
        }

    def write_plan(self, plan: dict[str, Any]) -> None:
        self.plan_out.parent.mkdir(parents=True, exist_ok=True)
        self.plan_out.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def preflight(self, plan: dict[str, Any]) -> None:
        missing: list[str] = []
        for material in plan.get("required_materials", []):
            if not isinstance(material, dict):
                continue
            if bool(material.get("required", True)) is not True:
                continue
            kind = str(material.get("kind") or "").strip()
            value = str(material.get("value") or "").strip()
            if not value:
                missing.append("material:empty")
                continue
            if kind == "file" and not Path(value).exists():
                missing.append(f"file:{value}")
            elif kind == "tool" and not self._tool_exists(value):
                missing.append(f"tool:{value}")
            elif kind == "git" and value == "clean_worktree" and not self._git_is_clean():
                missing.append("git:dirty_worktree")

        missing_models = self._missing_models(plan)
        missing.extend(f"model:{token}" for token in missing_models)
        if missing:
            raise ArbiterFailure(
                phase="preflight",
                code=ERROR_PREFLIGHT,
                message="Required materials missing.",
                failures=missing,
            )

    def validate_run_output(self, *, path: Path, architect_model: str, auditor_model: str) -> None:
        if not path.exists():
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_SHAPE,
                message="Run artifact was not created.",
                failures=[f"missing_artifact:{path.as_posix()}"],
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_SHAPE,
                message="Run artifact is not valid JSON.",
                failures=[f"invalid_json:{path.as_posix()}:{exc.msg}"],
            ) from exc
        if not isinstance(payload, dict):
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_SHAPE,
                message="Run artifact has invalid top-level shape.",
                failures=[f"invalid_root_type:{path.as_posix()}"],
            )

        shape_failures = self._shape_failures(payload, architect_model=architect_model, auditor_model=auditor_model)
        if shape_failures:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_SHAPE,
                message="Shape validation failed.",
                failures=shape_failures,
                context={"artifact": path.as_posix()},
            )

        leak_failures = self._leak_failures(payload)
        if leak_failures:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_LEAK,
                message="Leak validation failed.",
                failures=leak_failures,
                context={"artifact": path.as_posix()},
            )

        trace_failures = self._trace_failures(payload)
        if trace_failures:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_TRACE,
                message="Trace completeness validation failed.",
                failures=trace_failures,
                context={"artifact": path.as_posix()},
            )

    def postflight(self, plan: dict[str, Any]) -> None:
        missing = []
        for artifact in plan.get("expected_artifacts", []):
            if not isinstance(artifact, str):
                continue
            if not Path(artifact).exists():
                missing.append(artifact)
        if missing:
            raise ArbiterFailure(
                phase="postflight",
                code=ERROR_POSTFLIGHT,
                message="Expected artifacts were not produced.",
                failures=[f"missing_artifact:{item}" for item in sorted(missing)],
            )

    def emit_error_artifact(self, failure: ArbiterFailure) -> None:
        payload = {
            "schema_version": "odr.run_arbiter.error.v1",
            "status": "FAIL",
            "phase": failure.phase,
            "code": failure.code,
            "message": failure.message,
            "failures": sorted(failure.failures),
            "context": failure.context,
        }
        self.error_out.parent.mkdir(parents=True, exist_ok=True)
        self.error_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _slug(model_id: str) -> str:
        chars = [ch.lower() if ch.isalnum() else "_" for ch in str(model_id or "").strip()]
        token = "".join(chars).strip("_")
        while "__" in token:
            token = token.replace("__", "_")
        return token or "model"

    @staticmethod
    def _tool_exists(value: str) -> bool:
        token = str(value).strip()
        if not token:
            return False
        candidate = Path(token)
        if candidate.is_absolute() or candidate.parent != Path("."):
            return candidate.exists()
        return shutil.which(token) is not None

    def _missing_models(self, plan: dict[str, Any]) -> list[str]:
        required_models = [
            str(material.get("value") or "").strip()
            for material in plan.get("required_materials", [])
            if isinstance(material, dict) and str(material.get("kind") or "") == "model"
        ]
        required_models = sorted({item for item in required_models if item})
        if not required_models:
            return []

        result = subprocess.run(
            ["ollama", "list"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return required_models
        installed = self._parse_ollama_list(result.stdout or "")
        return [model for model in required_models if model not in installed]

    @staticmethod
    def _git_is_clean() -> bool:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False
        return not bool(str(result.stdout or "").strip())

    @staticmethod
    def _parse_ollama_list(text: str) -> set[str]:
        installed: set[str] = set()
        lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
        for line in lines[1:]:
            token = line.split()[0].strip()
            if token:
                installed.add(token)
        return installed

    @staticmethod
    def _shape_failures(payload: dict[str, Any], *, architect_model: str, auditor_model: str) -> list[str]:
        failures: list[str] = []
        results = payload.get("results")
        if not isinstance(results, list) or len(results) != 1:
            failures.append("results:expected_single_pair_result")
            return failures
        row = results[0]
        if not isinstance(row, dict):
            failures.append("results:0:not_object")
            return failures
        if str(row.get("architect_model") or "") != architect_model:
            failures.append(f"results:0:architect_model_mismatch:{architect_model}")
        if str(row.get("auditor_model") or "") != auditor_model:
            failures.append(f"results:0:auditor_model_mismatch:{auditor_model}")
        scenarios = row.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            failures.append("results:0:scenarios:missing_or_empty")
            return failures
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict):
                failures.append(f"results:0:scenarios:{index}:not_object")
                continue
            if not isinstance(scenario.get("final_state"), dict):
                failures.append(f"results:0:scenarios:{index}:final_state_missing")
            if not isinstance(scenario.get("rounds"), list):
                failures.append(f"results:0:scenarios:{index}:rounds_missing")
        return failures

    @staticmethod
    def _leak_failures(payload: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        for r_index, result in enumerate(payload.get("results", [])):
            if not isinstance(result, dict):
                continue
            for s_index, scenario in enumerate(result.get("scenarios", [])):
                if not isinstance(scenario, dict):
                    continue
                for round_row in scenario.get("rounds", []):
                    if not isinstance(round_row, dict):
                        continue
                    trace = round_row.get("odr_trace_record")
                    if not isinstance(trace, dict):
                        continue
                    if str(trace.get("stop_reason") or "") == "CODE_LEAK":
                        failures.append(f"results:{r_index}:scenarios:{s_index}:code_leak_stop")
                    metrics = trace.get("metrics")
                    if isinstance(metrics, dict) and bool(metrics.get("code_leak_hit")) is True:
                        failures.append(f"results:{r_index}:scenarios:{s_index}:code_leak_metric")
        return sorted(set(failures))

    @staticmethod
    def _trace_failures(payload: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        for r_index, result in enumerate(payload.get("results", [])):
            if not isinstance(result, dict):
                continue
            for s_index, scenario in enumerate(result.get("scenarios", [])):
                if not isinstance(scenario, dict):
                    continue
                rounds = scenario.get("rounds")
                if not isinstance(rounds, list):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:rounds_not_list")
                    continue
                for q_index, round_row in enumerate(rounds):
                    if not isinstance(round_row, dict):
                        failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:not_object")
                        continue
                    trace = round_row.get("odr_trace_record")
                    if not isinstance(trace, dict):
                        failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:trace_missing")
                        continue
                    if not isinstance(trace.get("metrics"), dict):
                        failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:trace_metrics_missing")
                    if "stop_reason" not in trace:
                        failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:trace_stop_reason_missing")
                final_state = scenario.get("final_state")
                if not isinstance(final_state, dict):
                    continue
                history_rounds = final_state.get("history_rounds")
                if not isinstance(history_rounds, list):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:final_state_history_rounds_missing")
                    continue
                history_round_count = final_state.get("history_round_count")
                if not isinstance(history_round_count, int):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:history_round_count_missing")
                    continue
                if history_round_count != len(history_rounds):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:history_round_count_mismatch")
                if history_round_count != len(rounds):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:round_count_mismatch")
        return sorted(set(failures))
