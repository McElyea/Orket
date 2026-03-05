from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from .artifacts import MarshallerArtifacts
from .canonical import compute_tree_digest, hash_canonical_json
from .contracts import PatchProposal, RunRequest
from .equivalence import compute_equivalence_key
from .gates import GateResult, resolve_gate_command, run_gate
from .intake import evaluate_patch_proposal
from .ledger import LedgerWriter
from .process import run_process
from .rejection_codes import PATCH_APPLY_FAILED, POLICY_DENY, SCHEMA_INVALID
from .runner_support import collect_gate_rejection_codes, metrics_payload, optional_positive_float


@dataclass(frozen=True)
class MarshallerRunOutcome:
    run_id: str
    accept: bool
    rejection_codes: tuple[str, ...]
    primary_rejection_code: str | None
    run_root_digest: str
    run_path: str
    decision_path: str


class MarshallerRunner:
    """Runs one Marshaller v0 attempt and records artifacts + ledger events."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    async def execute_once(
        self,
        *,
        run_id: str,
        run_request_payload: Mapping[str, Any],
        proposal_payload: Mapping[str, Any],
        allowed_paths: Sequence[str] = (),
    ) -> MarshallerRunOutcome:
        run_request = self._parse_run_request(run_request_payload)
        proposal = self._parse_proposal(proposal_payload)
        artifacts = MarshallerArtifacts(self.workspace_root, run_id)
        await artifacts.ensure_layout()
        ledger = LedgerWriter(artifacts.run_root / "ledger.jsonl")

        run_json = {
            "run_contract_version": "marshaller.run.v0",
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "request": run_request.model_dump(mode="json"),
        }
        await artifacts.write_run_json(run_json)
        await ledger.append(
            "run_started",
            {
                "run_id": run_id,
                "run_contract_version": run_json["run_contract_version"],
            },
        )

        attempt_index = 1
        await artifacts.write_proposal(attempt_index, proposal.model_dump(mode="json"))
        patch_path = await artifacts.write_patch(attempt_index, proposal.patch)
        await ledger.append(
            "attempt_started",
            {
                "attempt_index": attempt_index,
                "proposal_id": proposal.proposal_id,
            },
        )

        intake = evaluate_patch_proposal(
            proposal.model_dump(mode="json"),
            allowed_paths=tuple(allowed_paths),
        )
        if not intake.ok:
            return await self._complete_rejection(
                artifacts=artifacts,
                ledger=ledger,
                run_id=run_id,
                attempt_index=attempt_index,
                rejection_codes=intake.rejection_codes,
                gate_results=(),
                tree_digest="",
                apply_result={"ok": False, "reason": "intake_rejected"},
            )

        apply_result = await self._apply_patch(run_request, proposal, patch_path, artifacts.attempt_dir(attempt_index))
        await artifacts.write_apply_result(attempt_index, apply_result)
        if not apply_result.get("ok", False):
            return await self._complete_rejection(
                artifacts=artifacts,
                ledger=ledger,
                run_id=run_id,
                attempt_index=attempt_index,
                rejection_codes=(PATCH_APPLY_FAILED,),
                gate_results=(),
                tree_digest="",
                apply_result=apply_result,
            )

        clone_path = Path(str(apply_result["clone_path"]))
        gate_results = await self._run_gates(run_request, clone_path, artifacts, attempt_index)
        rejection_codes = tuple(code for code in collect_gate_rejection_codes(gate_results) if code)
        tree_digest = await asyncio.to_thread(compute_tree_digest, clone_path)
        await artifacts.write_tree_digest(attempt_index, tree_digest)

        if rejection_codes:
            return await self._complete_rejection(
                artifacts=artifacts,
                ledger=ledger,
                run_id=run_id,
                attempt_index=attempt_index,
                rejection_codes=rejection_codes,
                gate_results=gate_results,
                tree_digest=tree_digest,
                apply_result=apply_result,
            )

        decision = self._build_decision(
            run_id=run_id,
            attempt_index=attempt_index,
            run_request=run_request,
            proposal=proposal,
            gate_results=gate_results,
            tree_digest=tree_digest,
            rejection_codes=(),
        )
        await artifacts.write_metrics(attempt_index, metrics_payload(gate_results, accepted=True))
        await artifacts.write_decision(attempt_index, decision)
        await ledger.append(
            "attempt_completed",
            {
                "attempt_index": attempt_index,
                "accept": True,
                "rejection_codes": [],
            },
        )
        await ledger.append(
            "run_completed",
            {
                "run_id": run_id,
                "accept": True,
                "run_root_digest": ledger.current_digest,
            },
        )
        return MarshallerRunOutcome(
            run_id=run_id,
            accept=True,
            rejection_codes=(),
            primary_rejection_code=None,
            run_root_digest=ledger.current_digest,
            run_path=str(artifacts.run_root),
            decision_path=str(artifacts.attempt_dir(attempt_index) / "decision.json"),
        )

    async def _run_gates(
        self,
        run_request: RunRequest,
        clone_path: Path,
        artifacts: MarshallerArtifacts,
        attempt_index: int,
    ) -> tuple[GateResult, ...]:
        results: list[GateResult] = []
        task_spec = run_request.task_spec
        flake_policy = task_spec.get("flake_policy") if isinstance(task_spec.get("flake_policy"), dict) else {}
        flake_mode = str(flake_policy.get("mode", "retry_then_deny")).strip() or "retry_then_deny"
        max_retries = int(flake_policy.get("max_retries", 2))
        timeout_seconds = optional_positive_float(task_spec.get("gate_timeout_seconds"))
        env = {str(k): str(v) for k, v in (task_spec.get("gate_env") or {}).items()} if isinstance(task_spec.get("gate_env"), dict) else {}

        for check_name in run_request.checks:
            command = resolve_gate_command(task_spec, check_name)
            if not command:
                synthetic = GateResult(
                    name=check_name,
                    command=(),
                    attempts=(),
                    passed=False,
                    flake_detected=False,
                    rejection_code=POLICY_DENY,
                )
                await artifacts.write_check(
                    attempt_index,
                    check_name,
                    synthetic.to_summary(),
                    f"Missing gate command for check '{check_name}'\n",
                )
                results.append(synthetic)
                continue
            result = await run_gate(
                name=check_name,
                command=command,
                cwd=clone_path,
                env=env,
                flake_mode=flake_mode,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
            await artifacts.write_check(attempt_index, check_name, result.to_summary(), result.log_text)
            results.append(result)
        return tuple(results)

    async def _apply_patch(
        self,
        run_request: RunRequest,
        proposal: PatchProposal,
        patch_path: Path,
        attempt_dir: Path,
    ) -> dict[str, Any]:
        repo_path = Path(run_request.repo_path)
        if not await asyncio.to_thread(repo_path.exists):
            return {"ok": False, "reason": f"repo_path does not exist: {repo_path}"}

        head = await run_process(("git", "rev-parse", "HEAD"), cwd=repo_path)
        if head.returncode != 0:
            return {"ok": False, "reason": "failed to resolve base repository HEAD", "stderr": head.stderr}
        head_digest = head.stdout.strip()
        if head_digest != proposal.base_revision_digest:
            return {
                "ok": False,
                "reason": "base revision mismatch",
                "expected_base_revision_digest": proposal.base_revision_digest,
                "observed_head_digest": head_digest,
            }

        clone_path = attempt_dir / "workspace_clone"
        await asyncio.to_thread(shutil.rmtree, clone_path, True)
        clone_result = await run_process(
            ("git", "clone", "--quiet", str(repo_path), str(clone_path)),
            cwd=attempt_dir,
        )
        if clone_result.returncode != 0:
            return {"ok": False, "reason": "git clone failed", "stderr": clone_result.stderr}

        checkout_result = await run_process(
            ("git", "checkout", "--detach", proposal.base_revision_digest),
            cwd=clone_path,
        )
        if checkout_result.returncode != 0:
            return {"ok": False, "reason": "git checkout failed", "stderr": checkout_result.stderr}

        apply_check = await run_process(
            ("git", "apply", "--check", str(patch_path)),
            cwd=clone_path,
        )
        if apply_check.returncode != 0:
            return {"ok": False, "reason": "patch check failed", "stderr": apply_check.stderr}

        apply_result = await run_process(("git", "apply", str(patch_path)), cwd=clone_path)
        if apply_result.returncode != 0:
            return {"ok": False, "reason": "patch apply failed", "stderr": apply_result.stderr}

        return {
            "ok": True,
            "clone_path": str(clone_path),
            "head_digest": head_digest,
        }

    async def _complete_rejection(
        self,
        *,
        artifacts: MarshallerArtifacts,
        ledger: LedgerWriter,
        run_id: str,
        attempt_index: int,
        rejection_codes: tuple[str, ...],
        gate_results: tuple[GateResult, ...],
        tree_digest: str,
        apply_result: dict[str, Any],
    ) -> MarshallerRunOutcome:
        await artifacts.write_apply_result(attempt_index, apply_result)
        if tree_digest:
            await artifacts.write_tree_digest(attempt_index, tree_digest)
        decision = self._build_decision(
            run_id=run_id,
            attempt_index=attempt_index,
            run_request=None,
            proposal=None,
            gate_results=gate_results,
            tree_digest=tree_digest,
            rejection_codes=rejection_codes,
        )
        await artifacts.write_metrics(attempt_index, metrics_payload(gate_results, accepted=False))
        await artifacts.write_decision(attempt_index, decision)
        await ledger.append(
            "attempt_completed",
            {
                "attempt_index": attempt_index,
                "accept": False,
                "rejection_codes": list(rejection_codes),
            },
        )
        await ledger.append(
            "run_completed",
            {
                "run_id": run_id,
                "accept": False,
                "run_root_digest": ledger.current_digest,
                "primary_rejection_code": rejection_codes[0] if rejection_codes else None,
            },
        )
        return MarshallerRunOutcome(
            run_id=run_id,
            accept=False,
            rejection_codes=rejection_codes,
            primary_rejection_code=rejection_codes[0] if rejection_codes else None,
            run_root_digest=ledger.current_digest,
            run_path=str(artifacts.run_root),
            decision_path=str(artifacts.attempt_dir(attempt_index) / "decision.json"),
        )

    def _build_decision(
        self,
        *,
        run_id: str,
        attempt_index: int,
        run_request: RunRequest | None,
        proposal: PatchProposal | None,
        gate_results: tuple[GateResult, ...],
        tree_digest: str,
        rejection_codes: tuple[str, ...],
    ) -> dict[str, Any]:
        gate_results_normalized = [
            {
                "name": row.name,
                "passed": row.passed,
                "flake_detected": row.flake_detected,
                "rejection_code": row.rejection_code,
            }
            for row in gate_results
        ]
        proposal_digest = hash_canonical_json(proposal.model_dump(mode="json")) if proposal else ""
        policy_version = "v0"
        policy_digest = ""
        base_revision_digest = ""
        if run_request:
            policy_version = str(run_request.task_spec.get("policy_version", "v0"))
            policy_digest = str(run_request.task_spec.get("policy_digest", ""))
        if proposal:
            base_revision_digest = proposal.base_revision_digest

        return {
            "decision_contract_version": "marshaller.decision.v0",
            "run_id": run_id,
            "attempt_index": attempt_index,
            "accept": not rejection_codes,
            "rejection_codes": list(rejection_codes),
            "primary_rejection_code": rejection_codes[0] if rejection_codes else None,
            "proposal_digest": proposal_digest,
            "policy_version": policy_version,
            "policy_digest": policy_digest,
            "equivalence_key": compute_equivalence_key(
                base_revision_digest=base_revision_digest,
                proposal_digest=proposal_digest,
                policy_version=policy_version,
                gate_results_normalized=gate_results_normalized,
            ),
            "tree_digest": tree_digest,
            "gate_results_normalized": gate_results_normalized,
        }

    @staticmethod
    def _parse_run_request(payload: Mapping[str, Any]) -> RunRequest:
        try:
            return RunRequest.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"{SCHEMA_INVALID}: {exc}") from exc

    @staticmethod
    def _parse_proposal(payload: Mapping[str, Any]) -> PatchProposal:
        try:
            return PatchProposal.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(f"{SCHEMA_INVALID}: {exc}") from exc
