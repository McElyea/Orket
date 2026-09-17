from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.application.services.control_plane_workload_catalog import (  # noqa: E402 - repository CLI bootstrap
    _resolve_odr_arbiter_control_plane_workload_from_contract,
)
from orket.core.contracts import (  # noqa: E402 - repository CLI bootstrap
    WORKLOAD_CONTRACT_VERSION_V1,
    parse_workload_contract,
)
from orket.runtime.config.provider_runtime_target import (  # noqa: E402 - repository CLI bootstrap
    ProviderRuntimeWarmupError,
)
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402 - repository CLI bootstrap
from scripts.odr.provider_admission import (  # noqa: E402 - repository CLI bootstrap
    ProviderSelection,
    available_models,
    provider_evidence_failures,
    resolve_selection,
    selection_from_plan,
)
from scripts.odr.run_artifact_validation import (  # noqa: E402 - repository CLI bootstrap
    leak_failures,
    shape_failures,
    trace_failures,
)

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
        provider_selection: ProviderSelection | None = None,
    ) -> dict[str, Any]:
        selection = provider_selection or resolve_selection()
        run_pairs = self._run_pairs(out_dir, architects, auditors)
        materials: list[PlanMaterial] = [
            PlanMaterial(kind="tool", value=python_bin),
            PlanMaterial(kind="provider", value=selection.provider),
            PlanMaterial(kind="endpoint", value=selection.base_url),
            PlanMaterial(kind="file", value=str(base_spec.as_posix())),
            PlanMaterial(kind="file", value="scripts/odr/run_odr_live_role_matrix.py"),
            PlanMaterial(kind="file", value="scripts/odr/generate_odr_role_matrix_index.py"),
        ]
        if require_provenance:
            materials.append(PlanMaterial(kind="file", value="scripts/odr/generate_odr_provenance.py"))
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
        control_plane_workload_record = _resolve_odr_arbiter_control_plane_workload_from_contract(
            contract_payload=workload_contract,
            output_contract_ref=str(index_out.as_posix()),
            runner="run_odr_quant_sweep.py",
        ).model_dump(mode="json")

        return {
            "schema_version": "odr.run_arbiter.plan.v2",
            "provider_selection": selection.to_payload(),
            "runner": "run_odr_quant_sweep.py",
            "required_materials": [item.as_dict() for item in materials],
            "run_pairs": run_pairs,
            "expected_artifacts": sorted(expected_artifacts),
            "workload_contract": workload_contract,
            "control_plane_workload_record": control_plane_workload_record,
        }

    def _run_pairs(self, out_dir: Path, architects: list[str], auditors: list[str]) -> list[dict[str, str]]:
        return [{"architect_model": architect, "auditor_model": auditor,
                 "artifact": (out_dir / f"odr_live_role_matrix.{self._slug(architect)}_{self._slug(auditor)}.json").as_posix()}
                for architect in architects for auditor in auditors]

    def write_plan(self, plan: dict[str, Any]) -> None:
        write_payload_with_diff_ledger(self.plan_out, plan)

    def preflight(self, plan: dict[str, Any]) -> None:
        try:
            selection_from_plan(plan)
        except ValueError as exc:
            raise ArbiterFailure(phase="preflight", code=ERROR_PREFLIGHT,
                message="ODR plan provider admission is invalid.", failures=["provider_selection_invalid"]) from exc
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

        if not missing:
            missing.extend(f"model:{token}" for token in self._missing_models(plan))
        if missing:
            raise ArbiterFailure(
                phase="preflight",
                code=ERROR_PREFLIGHT,
                message="Required materials missing.",
                failures=missing,
            )

    def validate_run_output(self, *, path: Path, architect_model: str, auditor_model: str,
                            provider_selection: ProviderSelection) -> None:
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

        shape_errors = shape_failures(payload, architect_model=architect_model, auditor_model=auditor_model)
        if not shape_errors:
            shape_errors = provider_evidence_failures(payload, provider_selection, architect_model, auditor_model)
        if shape_errors:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_SHAPE,
                message="Shape validation failed.",
                failures=shape_errors,
                context={"artifact": path.as_posix()},
            )

        leak_errors = leak_failures(payload)
        if leak_errors:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_LEAK,
                message="Leak validation failed.",
                failures=leak_errors,
                context={"artifact": path.as_posix()},
            )

        trace_errors = trace_failures(payload)
        if trace_errors:
            raise ArbiterFailure(
                phase="execution",
                code=ERROR_TRACE,
                message="Trace completeness validation failed.",
                failures=trace_errors,
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
        write_payload_with_diff_ledger(self.error_out, payload)

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
        if candidate.is_absolute() or candidate.parent != Path():
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

        try:
            selection = selection_from_plan(plan)
            installed = asyncio.run(available_models(selection))
        except (httpx.HTTPError, ProviderRuntimeWarmupError, OSError, ValueError) as exc:
            raise ArbiterFailure(
                phase="preflight", code=ERROR_PREFLIGHT, message="Provider model discovery unavailable.",
                failures=[f"provider_discovery:{type(exc).__name__}"],
            ) from exc
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
