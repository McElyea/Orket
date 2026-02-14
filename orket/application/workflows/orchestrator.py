import asyncio
import json
import uuid
import re
from types import SimpleNamespace
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
from collections import defaultdict

from orket.schema import (
    EpicConfig, TeamConfig, EnvironmentConfig, IssueConfig,
    CardStatus, RoleConfig, DialectConfig, SkillConfig
)
from orket.application.workflows.turn_executor import TurnExecutor
from orket.orchestration.models import ModelSelector
from orket.orchestration.notes import NoteStore, Note
from orket.decision_nodes.contracts import PlanningInput
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.application.services.prompt_compiler import PromptCompiler
from orket.core.policies.tool_gate import ToolGate
from orket.core.contracts.repositories import CardRepository, SnapshotRepository
from orket.adapters.storage.async_repositories import AsyncPendingGateRepository
from orket.tools import ToolBox, get_tool_map
from orket.logging import log_event
from orket.exceptions import ExecutionFailed
from orket.core.domain.state_machine import StateMachine
from orket.core.domain.guard_review import GuardReviewPayload
from orket.utils import sanitize_name

class Orchestrator:
    """
    The Next-Gen Orchestrator Service.
    Decomposes the Traction Loop from the ExecutionPipeline.
    
    Responsibilities:
    - Managing the execution lifecycle of an Epic or Rock.
    - Handling parallel execution of independent tasks (DAG).
    - Managing turn-based state transitions and persistence.
    """
    def __init__(
        self,
        workspace: Path,
        async_cards: CardRepository,
        snapshots: SnapshotRepository,
        org: Any,
        config_root: Path,
        db_path: str,
        loader: Any, # ConfigLoader
        sandbox_orchestrator: Any # SandboxOrchestrator
    ):
        self.workspace = workspace
        self.async_cards = async_cards
        self.snapshots = snapshots
        self.org = org
        self.config_root = config_root
        self.db_path = db_path
        self.loader = loader
        self.sandbox_orchestrator = sandbox_orchestrator
        
        # Phase 6.4: Persistent Memory
        from orket.services.memory_store import MemoryStore
        memory_db = Path(db_path).parent / "project_memory.db"
        self.memory = MemoryStore(memory_db)
        
        # Internal state
        self.notes = NoteStore()
        self.transcript = []
        self._sandbox_locks = defaultdict(asyncio.Lock)
        self.pending_gates = AsyncPendingGateRepository(self.db_path)
        self.decision_nodes = DecisionNodeRegistry()
        self.planner_node = self.decision_nodes.resolve_planner(self.org)
        self.router_node = self.decision_nodes.resolve_router(self.org)
        self.evaluator_node = self.decision_nodes.resolve_evaluator(self.org)
        self.loop_policy_node = self.decision_nodes.resolve_orchestration_loop(self.org)
        self.context_window = self.loop_policy_node.context_window(self.org)
        self.model_client_node = self.decision_nodes.resolve_model_client(self.org)

    def _history_context(self) -> List[Dict[str, str]]:
        return [{"role": t.role, "content": t.content} for t in self.transcript[-self.context_window:]]

    async def verify_issue(self, issue_id: str, run_id: str | None = None) -> Any:
        """
        Runs empirical verification for a specific issue.
        """
        from orket.domain.verification import VerificationResult, VerificationEngine
        from orket.domain.sandbox import SandboxStatus
        
        # 1. Load the latest IssueConfig from DB
        issue_data = await self.async_cards.get_by_id(issue_id)
        if not issue_data:
            from orket.exceptions import CardNotFound
            raise CardNotFound(f"Cannot verify non-existent issue {issue_id}")
            
        issue = IssueConfig.model_validate(issue_data.model_dump())
        
        # 2. Execute Verification (Fixtures)
        verification_event = {"issue_id": issue_id}
        if run_id:
            verification_event["run_id"] = run_id
        log_event("verification_started", verification_event, self.workspace)
        result = await asyncio.to_thread(VerificationEngine.verify, issue.verification, self.workspace)
        
        # 3. Optional: Execute Sandbox Verification (HTTP)
        rock_id = issue.build_id
        sandbox = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
        if sandbox and sandbox.status == SandboxStatus.RUNNING:
            sandbox_event = {"issue_id": issue_id}
            if run_id:
                sandbox_event["run_id"] = run_id
            log_event("verification_sandbox_started", sandbox_event, self.workspace)
            sb_result = await VerificationEngine.verify_sandbox(sandbox, issue.verification)
            # Merge results
            result.passed += sb_result.passed
            result.failed += sb_result.failed
            result.total_scenarios += sb_result.total_scenarios
            result.logs.extend(sb_result.logs)

        # 4. Update the Issue with the new verification state
        issue.verification.last_run = result
        await self.async_cards.save(issue.model_dump())
        return result

    async def _trigger_sandbox(self, epic: EpicConfig, run_id: str | None = None):
        """Helper to trigger sandbox deployment with per-epic locking."""
        from orket.domain.sandbox import TechStack, SandboxStatus
        rock_id = epic.parent_id or epic.id
        
        async with self._sandbox_locks[rock_id]:
            # Double-check if already running under the lock
            existing = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
            if existing and existing.status == SandboxStatus.RUNNING:
                return

            deploy_start = {"rock_id": rock_id}
            if run_id:
                deploy_start["run_id"] = run_id
            log_event("sandbox_deploy_started", deploy_start, self.workspace)
            try:
                await self.sandbox_orchestrator.create_sandbox(
                    rock_id=rock_id,
                    project_name=epic.name,
                    tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                    workspace_path=str(self.workspace)
                )
            except (RuntimeError, ValueError, OSError) as e:
                deploy_failed = {"rock_id": rock_id, "error": str(e)}
                if run_id:
                    deploy_failed["run_id"] = run_id
                log_event("sandbox_deploy_failed", deploy_failed, self.workspace)

    async def execute_epic(
        self, 
        active_build: str, 
        run_id: str, 
        epic: EpicConfig, 
        team: TeamConfig, 
        env: EnvironmentConfig, 
        target_issue_id: str = None,
        resume_mode: bool = False,
    ):
        """
        Main execution loop for an Epic.
        Executes independent issues in parallel using a TAG-based DAG.
        """
        from orket.orchestration.models import ModelSelector
        from orket.settings import load_user_settings
        
        # 1. Setup Execution Environment
        settings_path = self.config_root / "user_settings.json"
        if settings_path.exists():
            user_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        else:
            user_settings = load_user_settings()
        model_selector = ModelSelector(organization=self.org, user_settings=user_settings)
        prompt_strategy_node = self.decision_nodes.resolve_prompt_strategy(model_selector, self.org)
        
        tool_gate = ToolGate(organization=self.org, workspace_root=self.workspace)
        executor = TurnExecutor(StateMachine(), tool_gate, self.workspace)
        
        from orket.policy import create_session_policy
        policy = create_session_policy(str(self.workspace), epic.references)
        toolbox = ToolBox(
            policy,
            str(self.workspace),
            epic.references,
            db_path=self.db_path,
            cards_repo=self.async_cards,
            tool_gate=tool_gate,
            organization=self.org,
            decision_nodes=self.decision_nodes,
        )
        
        # Concurrency/loop control via loop policy node.
        concurrency_limit = self.loop_policy_node.concurrency_limit(self.org)
        semaphore = asyncio.Semaphore(concurrency_limit)

        log_event("orchestrator_hyper_loop_start", {"epic": epic.name, "run_id": run_id, "concurrency": concurrency_limit}, self.workspace)

        iteration_count = 0
        max_iterations = self.loop_policy_node.max_iterations(self.org)

        while iteration_count < max_iterations:
            iteration_count += 1
            
            backlog = await self.async_cards.get_by_build(active_build)
            independent_ready = await self.async_cards.get_independent_ready_issues(active_build)
            candidates = self.planner_node.plan(
                PlanningInput(
                    backlog=backlog,
                    independent_ready=independent_ready,
                    target_issue_id=target_issue_id,
                )
            )

            if not candidates:
                propagated_count = await self._propagate_dependency_blocks(backlog, run_id)
                if propagated_count:
                    continue

                # Empty-candidate policy (seam) with backward-compatible fallback.
                outcome_fn = getattr(self.loop_policy_node, "no_candidate_outcome", None)
                if callable(outcome_fn):
                    outcome = outcome_fn(backlog)
                else:
                    is_done = self.loop_policy_node.is_backlog_done(backlog)
                    outcome = {"is_done": is_done, "event_name": "orchestrator_epic_complete" if is_done else None}

                if outcome.get("is_done"):
                    event_name = outcome.get("event_name")
                    if event_name:
                        log_event(event_name, {"epic": epic.name, "run_id": run_id}, self.workspace)
                    break

                backlog_snapshot = [
                    {
                        "id": getattr(item, "id", "unknown"),
                        "status": (
                            getattr(item.status, "value", str(item.status))
                            if hasattr(item, "status")
                            else "unknown"
                        ),
                    }
                    for item in backlog
                ]
                reason = outcome.get("reason") or "No executable candidates while backlog incomplete."
                log_event(
                    "orchestrator_stalled",
                    {
                        "run_id": run_id,
                        "epic": epic.name,
                        "iteration": iteration_count,
                        "reason": reason,
                        "backlog": backlog_snapshot,
                    },
                    self.workspace,
                )
                raise ExecutionFailed(reason)
            
            log_event(
                "orchestrator_tick",
                {"run_id": run_id, "candidate_count": len(candidates), "iteration": iteration_count},
                self.workspace,
            )

            # 2. Parallel Dispatch with Semaphore
            async def semaphore_wrapper(issue_data):
                async with semaphore:
                    return await self._execute_issue_turn(
                        issue_data, epic, team, env, run_id, active_build, 
                        prompt_strategy_node, executor, toolbox, resume_mode=resume_mode
                    )

            await asyncio.gather(*(semaphore_wrapper(c) for c in candidates))

        if iteration_count >= max_iterations:
            final_backlog = await self.async_cards.get_by_build(active_build)
            exhaustion_fn = getattr(self.loop_policy_node, "should_raise_exhaustion", None)
            if callable(exhaustion_fn):
                should_raise = exhaustion_fn(iteration_count, max_iterations, final_backlog)
            else:
                should_raise = not self.loop_policy_node.is_backlog_done(final_backlog)
            if should_raise:
                raise ExecutionFailed(f"Hyper-Loop exhausted iterations ({max_iterations})")

    async def _propagate_dependency_blocks(self, backlog: List[Any], run_id: str) -> int:
        blocker_statuses = {CardStatus.BLOCKED, CardStatus.CANCELED, CardStatus.GUARD_REJECTED}
        status_by_id = {getattr(issue, "id", ""): getattr(issue, "status", None) for issue in backlog}
        propagated = []

        for issue in backlog:
            if getattr(issue, "status", None) != CardStatus.READY:
                continue
            depends_on = list(getattr(issue, "depends_on", []) or [])
            if not depends_on:
                continue
            blocked_by = [dep_id for dep_id in depends_on if status_by_id.get(dep_id) in blocker_statuses]
            if not blocked_by:
                continue

            await self.async_cards.update_status(
                issue.id,
                CardStatus.BLOCKED,
                reason="dependency_blocked",
                metadata={"run_id": run_id, "blocked_by": blocked_by},
            )
            issue.status = CardStatus.BLOCKED
            propagated.append({"issue_id": issue.id, "blocked_by": blocked_by})

        if propagated:
            log_event(
                "dependency_block_propagated",
                {"run_id": run_id, "updates": propagated},
                self.workspace,
            )
        return len(propagated)

    async def _execute_issue_turn(
        self, 
        issue_data: Any, 
        epic: EpicConfig, 
        team: TeamConfig, 
        env: EnvironmentConfig, 
        run_id: str, 
        active_build: str,
        prompt_strategy_node: Any,
        executor: TurnExecutor,
        toolbox: ToolBox,
        resume_mode: bool = False,
    ):
        """Executes a single turn for one issue."""
        issue = IssueConfig.model_validate(issue_data.model_dump())
        is_review_turn = self.loop_policy_node.is_review_turn(issue.status)
        
        # RUN EMPIRICAL VERIFICATION (FIT) for review turns
        if is_review_turn:
            verification_result = await self.verify_issue(issue.id, run_id=run_id)
            v_msg = f"EMPIRICAL VERIFICATION RESULT: {verification_result.passed}/{verification_result.total_scenarios} Passed."
            self.notes.add(Note(from_role="system", content=v_msg, step_index=len(self.transcript)))

        # Select Seat via router decision node
        seat_name = self.router_node.route(issue, team, is_review_turn)

        seat_obj = team.seats.get(sanitize_name(seat_name))
        if not seat_obj:
            await self.async_cards.update_status(
                issue.id,
                self.loop_policy_node.missing_seat_status(),
                reason="missing_seat",
                metadata={"seat": seat_name, "run_id": run_id},
            )
            return

        is_guard_turn = is_review_turn and ("integrity_guard" in list(seat_obj.roles))
        turn_status = self.loop_policy_node.turn_status_for_issue(is_review_turn)
        if is_guard_turn:
            turn_status = CardStatus.AWAITING_GUARD_REVIEW
        await self.async_cards.update_status(
            issue.id,
            turn_status,
            assignee=seat_name,
            reason="turn_dispatch",
            metadata={"run_id": run_id, "review_turn": is_review_turn},
        )

        # Prepare Role & Model
        roles_to_load = self.loop_policy_node.role_order_for_turn(list(seat_obj.roles), is_review_turn)

        role_config = self.loader.load_asset("roles", roles_to_load[0], RoleConfig)
        selected_model = prompt_strategy_node.select_model(role=roles_to_load[0], asset_config=epic)
        dialect_name = prompt_strategy_node.select_dialect(selected_model)
        dialect = self.loader.load_asset("dialects", dialect_name, DialectConfig)
        
        provider = self.model_client_node.create_provider(selected_model, env)
        client = self.model_client_node.create_client(provider)

        # Compile Prompt
        skill = SkillConfig(
            name=role_config.name or seat_name,
            intent=role_config.description,
            responsibilities=[ro.description for ro in [role_config]],
            tools=role_config.tools
        )
        # Phase 6.4: RAG (Memory Context)
        search_query = (issue.name or "") + " " + (issue.note or "")
        memories = await self.memory.search(search_query.strip())
        memory_context = "\n".join([f"- {m['content']}" for m in memories])
        
        system_desc = PromptCompiler.compile(skill, dialect)
        if memory_context:
            system_desc += f"\n\nPROJECT CONTEXT (PAST DECISIONS):\n{memory_context}"

        context = self._build_turn_context(
            run_id=run_id,
            issue=issue,
            seat_name=seat_name,
            roles_to_load=roles_to_load,
            turn_status=turn_status,
            selected_model=selected_model,
            resume_mode=resume_mode,
        )

        log_event(
            "orchestrator_dispatch",
            {"run_id": run_id, "seat": seat_name, "issue_id": issue.id, "status": issue.status.value},
            self.workspace,
        )
        result = await self._dispatch_turn(
            executor=executor,
            issue=issue,
            role_config=role_config,
            client=client,
            toolbox=toolbox,
            context=context,
            system_prompt=system_desc,
        )

        if result.success:
            self.transcript.append(result.turn)
            updated_issue = await self.async_cards.get_by_id(issue.id)
            if is_guard_turn:
                guard_payload = self._extract_guard_review_payload(result.turn.content or "")
                guard_event = self._resolve_guard_event(updated_issue.status)
                if guard_event == "guard_rejected":
                    guard_validation = self._validate_guard_rejection_payload(guard_payload)
                    if not guard_validation.get("valid", False):
                        request_id = await self._create_pending_gate_request(
                            run_id=run_id,
                            issue_id=issue.id,
                            seat_name=seat_name,
                            reason=str(guard_validation.get("reason") or "invalid_guard_payload"),
                            payload=guard_payload.model_dump(),
                            issue=issue,
                            turn_status=turn_status,
                        )
                        log_event(
                            "gate_request_created",
                            {
                                "run_id": run_id,
                                "request_id": request_id,
                                "issue_id": issue.id,
                                "seat": seat_name,
                                "request_type": "guard_rejection_payload",
                            },
                            self.workspace,
                        )
                        log_event(
                            "guard_payload_invalid",
                            {
                                "run_id": run_id,
                                "issue_id": issue.id,
                                "seat": seat_name,
                                "request_id": request_id,
                                "reason": guard_validation.get("reason"),
                                "payload": guard_payload.model_dump(),
                            },
                            self.workspace,
                        )
                        failure_result = SimpleNamespace(
                            error=(
                                "Deterministic failure: invalid guard rejection payload "
                                f"({guard_validation.get('reason')})."
                            ),
                            violations=[],
                        )
                        await self._handle_failure(issue, failure_result, run_id, roles_to_load)
                        return
                if guard_event:
                    log_event(
                        guard_event,
                        {
                            "run_id": run_id,
                            "issue_id": issue.id,
                            "seat": seat_name,
                            "review_payload": guard_payload.model_dump(),
                        },
                        self.workspace,
                    )
                    log_event(
                        "guard_review_payload",
                        {
                            "run_id": run_id,
                            "issue_id": issue.id,
                            "payload": guard_payload.model_dump(),
                        },
                        self.workspace,
                    )

            success_eval = self.evaluator_node.evaluate_success(
                issue=issue,
                updated_issue=updated_issue,
                turn=result.turn,
                seat_name=seat_name,
                is_review_turn=is_review_turn,
            )

            # Record significant turns in memory
            if success_eval.get("remember_decision"):
                await self.memory.remember(
                    content=f"Decision by {seat_name} on {issue.id}: {result.turn.content[:200]}...",
                    metadata={"issue_id": issue.id, "role": seat_name, "type": "decision"}
                )
            
            # Sandbox triggering
            success_actions = self.evaluator_node.success_post_actions(success_eval)
            if self.evaluator_node.should_trigger_sandbox(success_actions):
                await self._trigger_sandbox(epic, run_id=run_id)
                next_status = self.evaluator_node.next_status_after_success(success_actions)
                if next_status is not None:
                    await self.async_cards.update_status(
                        issue.id,
                        next_status,
                        reason="post_success_evaluator",
                        metadata={"run_id": run_id, "seat": seat_name},
                    )
            
            await provider.clear_context()
            await self._save_checkpoint(run_id, epic, team, env, active_build)
        else:
            await self._handle_failure(issue, result, run_id, roles_to_load)

    def _validate_guard_rejection_payload(self, payload: GuardReviewPayload) -> Dict[str, Any]:
        validate_fn = getattr(self.loop_policy_node, "validate_guard_rejection_payload", None)
        if callable(validate_fn):
            try:
                return dict(validate_fn(payload=payload))
            except TypeError:
                return dict(validate_fn(payload))

        rationale = (payload.rationale or "").strip()
        actions = [item.strip() for item in (payload.remediation_actions or []) if item and item.strip()]
        if not rationale:
            return {"valid": False, "reason": "missing_rationale"}
        if not actions:
            return {"valid": False, "reason": "missing_remediation_actions"}
        return {"valid": True, "reason": None}

    async def _create_pending_gate_request(
        self,
        *,
        run_id: str,
        issue_id: str,
        seat_name: str,
        reason: str,
        payload: Dict[str, Any],
        issue: IssueConfig,
        turn_status: CardStatus,
    ) -> str:
        gate_mode = "auto"
        gate_mode_fn = getattr(self.loop_policy_node, "gate_mode_for_seat", None)
        if callable(gate_mode_fn):
            try:
                gate_mode = str(
                    gate_mode_fn(
                        seat_name=seat_name,
                        issue=issue,
                        turn_status=turn_status,
                    )
                )
            except TypeError:
                gate_mode = str(gate_mode_fn(seat_name))

        return await self.pending_gates.create_request(
            session_id=run_id,
            issue_id=issue_id,
            seat_name=seat_name,
            gate_mode=gate_mode,
            request_type="guard_rejection_payload",
            reason=reason,
            payload=payload,
        )

    async def _create_pending_tool_approval_request(
        self,
        *,
        run_id: str,
        issue: IssueConfig,
        seat_name: str,
        gate_mode: str,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> str:
        return await self.pending_gates.create_request(
            session_id=run_id,
            issue_id=issue.id,
            seat_name=seat_name,
            gate_mode=gate_mode,
            request_type="tool_approval",
            reason=f"approval_required_tool:{tool_name}",
            payload={
                "tool": tool_name,
                "args": tool_args,
                "issue_status": str(issue.status.value if hasattr(issue.status, "value") else issue.status),
            },
        )

    def _build_turn_context(
        self,
        run_id: str,
        issue: IssueConfig,
        seat_name: str,
        roles_to_load: List[str],
        turn_status: CardStatus,
        selected_model: str,
        resume_mode: bool = False,
    ) -> Dict[str, Any]:
        required_action_tools = []
        required_tools_fn = getattr(self.loop_policy_node, "required_action_tools_for_seat", None)
        if callable(required_tools_fn):
            try:
                required_action_tools = list(
                    required_tools_fn(
                        seat_name=seat_name,
                        issue=issue,
                        turn_status=turn_status,
                    )
                    or []
                )
            except TypeError:
                required_action_tools = list(required_tools_fn(seat_name) or [])

        required_statuses = []
        required_statuses_fn = getattr(self.loop_policy_node, "required_statuses_for_seat", None)
        if callable(required_statuses_fn):
            try:
                required_statuses = list(
                    required_statuses_fn(
                        seat_name=seat_name,
                        issue=issue,
                        turn_status=turn_status,
                    )
                    or []
                )
            except TypeError:
                required_statuses = list(required_statuses_fn(seat_name) or [])

        gate_mode = "auto"
        gate_mode_fn = getattr(self.loop_policy_node, "gate_mode_for_seat", None)
        if callable(gate_mode_fn):
            try:
                gate_mode = str(
                    gate_mode_fn(
                        seat_name=seat_name,
                        issue=issue,
                        turn_status=turn_status,
                    )
                )
            except TypeError:
                gate_mode = str(gate_mode_fn(seat_name))

        approval_required_tools = []
        approval_tools_fn = getattr(self.loop_policy_node, "approval_required_tools_for_seat", None)
        if callable(approval_tools_fn):
            try:
                approval_required_tools = list(
                    approval_tools_fn(
                        seat_name=seat_name,
                        issue=issue,
                        turn_status=turn_status,
                    )
                    or []
                )
            except TypeError:
                approval_required_tools = list(approval_tools_fn(seat_name) or [])

        if approval_required_tools and gate_mode == "auto":
            gate_mode = "approval_required"

        async def _pending_gate_request_writer(*, tool_name: str, tool_args: Dict[str, Any]) -> str:
            return await self._create_pending_tool_approval_request(
                run_id=run_id,
                issue=issue,
                seat_name=seat_name,
                gate_mode=gate_mode,
                tool_name=tool_name,
                tool_args=tool_args,
            )

        return {
            "session_id": run_id,
            "issue_id": issue.id,
            "workspace": str(self.workspace),
            "role": seat_name,
            "roles": roles_to_load,
            "current_status": turn_status.value,
            "selected_model": selected_model,
            "turn_index": len(self.transcript) + 1,
            "dependency_context": {
                "depends_on": issue.depends_on,
                "dependency_count": len(issue.depends_on),
            },
            "required_action_tools": required_action_tools,
            "required_statuses": required_statuses,
            "stage_gate_mode": gate_mode,
            "approval_required_tools": approval_required_tools,
            "create_pending_gate_request": _pending_gate_request_writer,
            "resume_mode": bool(resume_mode),
            "history": self._history_context(),
        }

    def _extract_guard_review_payload(self, content: str) -> GuardReviewPayload:
        blob = content or ""
        decoder = json.JSONDecoder()
        candidates: List[Dict[str, Any]] = []

        fenced_matches = re.findall(r"```json\s*([\s\S]*?)```", blob, flags=re.IGNORECASE)
        for chunk in fenced_matches:
            try:
                parsed = json.loads(chunk.strip())
                if isinstance(parsed, dict):
                    candidates.append(parsed)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        start = 0
        while True:
            brace_index = blob.find("{", start)
            if brace_index == -1:
                break
            try:
                parsed, end_pos = decoder.raw_decode(blob[brace_index:])
                if isinstance(parsed, dict):
                    candidates.append(parsed)
                start = brace_index + max(end_pos, 1)
            except json.JSONDecodeError:
                start = brace_index + 1

        for parsed in candidates:
            if {"rationale", "violations", "remediation_actions"} & set(parsed.keys()):
                try:
                    return GuardReviewPayload.model_validate(parsed)
                except (ValueError, TypeError):
                    continue
        return GuardReviewPayload(
            rationale=(blob.strip()[:500] if blob else "No rationale provided."),
            violations=[],
            remediation_actions=[],
        )

    def _resolve_guard_event(self, status: Any) -> Optional[str]:
        if status == CardStatus.DONE:
            return "guard_approved"
        if status in {CardStatus.BLOCKED, CardStatus.GUARD_REJECTED}:
            return "guard_rejected"
        if status in {CardStatus.IN_PROGRESS, CardStatus.GUARD_REQUESTED_CHANGES, CardStatus.READY_FOR_TESTING}:
            return "guard_requested_changes"
        return None

    async def _dispatch_turn(
        self,
        executor: TurnExecutor,
        issue: IssueConfig,
        role_config: RoleConfig,
        client: Any,
        toolbox: ToolBox,
        context: Dict[str, Any],
        system_prompt: str,
    ) -> Any:
        return await executor.execute_turn(
            issue,
            role_config,
            client,
            toolbox,
            context,
            system_prompt=system_prompt,
        )

    async def _save_checkpoint(self, run_id: str, epic: EpicConfig, team: TeamConfig, env: EnvironmentConfig, active_build: str):
        snapshot_data = {
            "epic": epic.model_dump(),
            "team": team.model_dump(),
            "env": env.model_dump(),
            "build_id": active_build,
            "timestamp": datetime.now(UTC).isoformat()
        }
        legacy_transcript = [
            {"role": t.role, "issue": t.issue_id, "content": t.content}
            for t in self.transcript
        ]
        await self.snapshots.record(run_id, snapshot_data, legacy_transcript)

    async def _handle_failure(self, issue: IssueConfig, result: Any, run_id: str, roles: List[str]):
        from orket.domain.failure_reporter import FailureReporter

        await FailureReporter.generate_report(
            workspace=self.workspace,
            session_id=run_id,
            card_id=issue.id,
            violation=result.error or "Unknown failure",
            transcript=self.transcript,
            roles=roles
        )

        eval_decision = self.evaluator_node.evaluate_failure(issue, result)
        issue.retry_count = eval_decision.get("next_retry_count", issue.retry_count)
        action = eval_decision.get("action")
        failure_exception_class = self.evaluator_node.failure_exception_class(action)

        # Mechanical governance violations are terminal for the issue.
        if action == "governance_violation":
            failure_status = self.evaluator_node.status_for_failure_action(action)
            await self.async_cards.update_status(
                issue.id,
                failure_status,
                reason="governance_violation",
                metadata={"run_id": run_id, "error": result.error},
            )
            issue.status = failure_status
            await self.async_cards.save(issue.model_dump())
            raise failure_exception_class(self.evaluator_node.governance_violation_message(result.error))

        if action == "catastrophic":
            event_name = self.evaluator_node.failure_event_name(action)
            if event_name:
                log_event(event_name, {
                    "run_id": run_id,
                    "issue_id": issue.id,
                    "retry_count": issue.retry_count,
                    "error": result.error
                }, self.workspace)
            failure_status = self.evaluator_node.status_for_failure_action(action)
            await self.async_cards.update_status(
                issue.id,
                failure_status,
                reason="catastrophic_failure",
                metadata={"run_id": run_id, "error": result.error},
            )
            await self.async_cards.save(issue.model_dump())
            
            # Catastrophic failure shuts down the session
            from orket.state import runtime_state
            if self.evaluator_node.should_cancel_session(action):
                task = await runtime_state.get_task(run_id)
                if task:
                    cancel_result = task.cancel()
                    if asyncio.iscoroutine(cancel_result):
                        await cancel_result
                
            raise failure_exception_class(
                self.evaluator_node.catastrophic_failure_message(issue.id, issue.max_retries)
            )

        if action != "retry":
            raise failure_exception_class(self.evaluator_node.unexpected_failure_action_message(action, issue.id))

        # Log retry and reset to READY
        event_name = self.evaluator_node.failure_event_name(action)
        if event_name:
            log_event(event_name, {
                "run_id": run_id,
                "issue_id": issue.id,
                "retry_count": issue.retry_count,
                "max_retries": issue.max_retries,
                "error": result.error
            }, self.workspace)
        
        await self.async_cards.update_status(
            issue.id,
            self.evaluator_node.status_for_failure_action(action),
            reason="retry_scheduled",
            metadata={
                "run_id": run_id,
                "retry_count": issue.retry_count,
                "max_retries": issue.max_retries,
                "error": result.error,
            },
        )
        await self.async_cards.save(issue.model_dump())

        raise failure_exception_class(
            self.evaluator_node.retry_failure_message(
                issue.id,
                issue.retry_count,
                issue.max_retries,
                result.error,
            )
        )


