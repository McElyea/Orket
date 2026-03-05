from __future__ import annotations

import asyncio
from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import MarshallerArtifacts
from .canonical import compute_tree_digest, hash_canonical_json
from .contracts import PatchProposal, RunRequest
from .equivalence import compute_equivalence_key
from .gates import GateResult, resolve_gate_command, run_gate
from .intake import evaluate_patch_proposal
from .ledger import LedgerWriter
from .process import run_process
from .rejection_codes import PATCH_APPLY_FAILED, POLICY_DENY
from .runner_support import collect_gate_rejection_codes, metrics_payload, optional_positive_float


@dataclass(frozen=True)
class AttemptResult:
    attempt_index: int
    accept: bool
    rejection_codes: tuple[str, ...]
    primary_rejection_code: str | None
    decision_path: str
    tree_digest: str


class AttemptRuntime:
    """Execute one proposal attempt and persist all attempt-level artifacts."""

    def __init__(
        self,
        *,
        run_id: str,
        run_request: RunRequest,
        artifacts: MarshallerArtifacts,
        allowed_paths: Sequence[str],
    ) -> None:
        self.run_id = run_id
        self.run_request = run_request
        self.artifacts = artifacts
        self.allowed_paths = tuple(allowed_paths)

    async def execute_attempt(
        self,
        *,
        ledger: LedgerWriter,
        attempt_index: int,
        proposal_payload: Mapping[str, Any],
    ) -> AttemptResult:
        raw_payload = dict(proposal_payload)
        await self.artifacts.write_proposal(attempt_index, raw_payload)
        patch_text = str(raw_payload.get("patch", "")) if isinstance(raw_payload.get("patch"), str) else ""
        patch_path = await self.artifacts.write_patch(attempt_index, patch_text)
        await ledger.append(
            "attempt_started",
            {
                "attempt_index": attempt_index,
                "proposal_id": str(raw_payload.get("proposal_id", "")),
            },
        )

        intake = evaluate_patch_proposal(raw_payload, allowed_paths=self.allowed_paths)
        proposal = intake.proposal
        if not intake.ok or proposal is None:
            return await self._finalize_attempt(
                ledger=ledger,
                attempt_index=attempt_index,
                proposal=proposal,
                rejection_codes=intake.rejection_codes,
                gate_results=(),
                tree_digest="",
                apply_result={"ok": False, "reason": "intake_rejected"},
            )

        apply_result = await self._apply_patch(proposal, patch_path, self.artifacts.attempt_dir(attempt_index))
        await self.artifacts.write_apply_result(attempt_index, apply_result)
        if not apply_result.get("ok", False):
            return await self._finalize_attempt(
                ledger=ledger,
                attempt_index=attempt_index,
                proposal=proposal,
                rejection_codes=(PATCH_APPLY_FAILED,),
                gate_results=(),
                tree_digest="",
                apply_result=apply_result,
            )

        clone_path = Path(str(apply_result["clone_path"]))
        gate_results = await self._run_gates(clone_path=clone_path, attempt_index=attempt_index)
        rejection_codes = tuple(code for code in collect_gate_rejection_codes(gate_results) if code)
        tree_digest = await asyncio.to_thread(compute_tree_digest, clone_path)
        await self.artifacts.write_tree_digest(attempt_index, tree_digest)
        return await self._finalize_attempt(
            ledger=ledger,
            attempt_index=attempt_index,
            proposal=proposal,
            rejection_codes=rejection_codes,
            gate_results=gate_results,
            tree_digest=tree_digest,
            apply_result=apply_result,
        )

    async def _finalize_attempt(
        self,
        *,
        ledger: LedgerWriter,
        attempt_index: int,
        proposal: PatchProposal | None,
        rejection_codes: tuple[str, ...],
        gate_results: tuple[GateResult, ...],
        tree_digest: str,
        apply_result: dict[str, Any],
    ) -> AttemptResult:
        await self.artifacts.write_apply_result(attempt_index, apply_result)
        if tree_digest:
            await self.artifacts.write_tree_digest(attempt_index, tree_digest)
        decision = self._build_decision(
            attempt_index=attempt_index,
            proposal=proposal,
            gate_results=gate_results,
            tree_digest=tree_digest,
            rejection_codes=rejection_codes,
        )
        await self.artifacts.write_metrics(
            attempt_index,
            metrics_payload(gate_results, accepted=not rejection_codes),
        )
        decision_path = self.artifacts.attempt_dir(attempt_index) / "decision.json"
        await self.artifacts.write_decision(attempt_index, decision)
        await ledger.append(
            "attempt_completed",
            {
                "attempt_index": attempt_index,
                "accept": not rejection_codes,
                "rejection_codes": list(rejection_codes),
            },
        )
        return AttemptResult(
            attempt_index=attempt_index,
            accept=not rejection_codes,
            rejection_codes=rejection_codes,
            primary_rejection_code=rejection_codes[0] if rejection_codes else None,
            decision_path=str(decision_path),
            tree_digest=tree_digest,
        )

    async def _run_gates(self, *, clone_path: Path, attempt_index: int) -> tuple[GateResult, ...]:
        results: list[GateResult] = []
        task_spec = self.run_request.task_spec
        flake_policy = task_spec.get("flake_policy") if isinstance(task_spec.get("flake_policy"), dict) else {}
        flake_mode = str(flake_policy.get("mode", "retry_then_deny")).strip() or "retry_then_deny"
        max_retries = int(flake_policy.get("max_retries", 2))
        timeout_seconds = optional_positive_float(task_spec.get("gate_timeout_seconds"))
        env = (
            {str(k): str(v) for k, v in (task_spec.get("gate_env") or {}).items()}
            if isinstance(task_spec.get("gate_env"), dict)
            else {}
        )

        for check_name in self.run_request.checks:
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
                await self.artifacts.write_check(
                    attempt_index,
                    check_name,
                    synthetic.to_summary(),
                    f"Missing gate command for check '{check_name}'\n",
                )
                results.append(synthetic)
                continue
            gate_result = await run_gate(
                name=check_name,
                command=command,
                cwd=clone_path,
                env=env,
                flake_mode=flake_mode,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
            )
            await self.artifacts.write_check(
                attempt_index,
                check_name,
                gate_result.to_summary(),
                gate_result.log_text,
            )
            results.append(gate_result)
        return tuple(results)

    async def _apply_patch(
        self,
        proposal: PatchProposal,
        patch_path: Path,
        attempt_dir: Path,
    ) -> dict[str, Any]:
        repo_path = Path(self.run_request.repo_path)
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

        apply_check = await run_process(("git", "apply", "--check", str(patch_path)), cwd=clone_path)
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

    def _build_decision(
        self,
        *,
        attempt_index: int,
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
        policy_version = str(self.run_request.task_spec.get("policy_version", "v0"))
        policy_digest = str(self.run_request.task_spec.get("policy_digest", ""))
        base_revision_digest = proposal.base_revision_digest if proposal else ""
        return {
            "decision_contract_version": "marshaller.decision.v0",
            "run_id": self.run_id,
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

