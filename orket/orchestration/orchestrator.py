import asyncio
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
from collections import defaultdict

from orket.schema import (
    EpicConfig, TeamConfig, EnvironmentConfig, IssueConfig,
    CardStatus, RoleConfig, DialectConfig, SkillConfig
)
from orket.infrastructure.async_card_repository import AsyncCardRepository
from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.infrastructure.async_repositories import AsyncSnapshotRepository
from orket.orchestration.turn_executor import TurnExecutor
from orket.orchestration.models import ModelSelector
from orket.orchestration.notes import NoteStore, Note
from orket.decision_nodes.contracts import PlanningInput
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.services.prompt_compiler import PromptCompiler
from orket.services.tool_gate import ToolGate
from orket.tools import ToolBox, get_tool_map
from orket.logging import log_event
from orket.exceptions import ExecutionFailed, GovernanceViolation
from orket.domain.state_machine import StateMachine
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
        async_cards: AsyncCardRepository,
        snapshots: AsyncSnapshotRepository,
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
        self.decision_nodes = DecisionNodeRegistry()
        self.planner_node = self.decision_nodes.resolve_planner(self.org)
        self.router_node = self.decision_nodes.resolve_router(self.org)
        self.evaluator_node = self.decision_nodes.resolve_evaluator(self.org)
        self.loop_policy_node = self.decision_nodes.resolve_orchestration_loop(self.org)
        self.context_window = self.loop_policy_node.context_window(self.org)
        self.model_client_node = self.decision_nodes.resolve_model_client(self.org)

    def _history_context(self) -> List[Dict[str, str]]:
        return [{"role": t.role, "content": t.content} for t in self.transcript[-self.context_window:]]

    async def verify_issue(self, issue_id: str) -> Any:
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
        print(f"  [ORCHESTRATOR] Running empirical tests for {issue_id}...")
        result = VerificationEngine.verify(issue.verification, self.workspace)
        
        # 3. Optional: Execute Sandbox Verification (HTTP)
        rock_id = issue.build_id
        sandbox = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
        if sandbox and sandbox.status == SandboxStatus.RUNNING:
            print(f"  [ORCHESTRATOR] Running sandbox HTTP tests for {issue_id}...")
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

    async def _trigger_sandbox(self, epic: EpicConfig):
        """Helper to trigger sandbox deployment with per-epic locking."""
        from orket.domain.sandbox import TechStack, SandboxStatus
        rock_id = epic.parent_id or epic.id
        
        async with self._sandbox_locks[rock_id]:
            # Double-check if already running under the lock
            existing = self.sandbox_orchestrator.registry.get(f"sandbox-{rock_id}")
            if existing and existing.status == SandboxStatus.RUNNING:
                return

            print(f"  [ORCHESTRATOR] Deploying environment for {rock_id}...")
            try:
                await self.sandbox_orchestrator.create_sandbox(
                    rock_id=rock_id,
                    project_name=epic.name,
                    tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                    workspace_path=str(self.workspace)
                )
            except (RuntimeError, ValueError, OSError) as e:
                print(f"  [ORCHESTRATOR] WARN: Deployment failed: {e}")

    async def execute_epic(
        self, 
        active_build: str, 
        run_id: str, 
        epic: EpicConfig, 
        team: TeamConfig, 
        env: EnvironmentConfig, 
        target_issue_id: str = None
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
            fs = AsyncFileTools(self.config_root)
            user_settings = json.loads(await fs.read_file("user_settings.json"))
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
                # Check if we are actually done or just blocked
                is_done = self.loop_policy_node.is_backlog_done(backlog)
                if is_done:
                    print(f"  [ORCHESTRATOR] Epic '{epic.name}' complete.")
                break
            
            print(f"  [TICK] Running {len(candidates)} tasks in parallel...")

            # 2. Parallel Dispatch with Semaphore
            async def semaphore_wrapper(issue_data):
                async with semaphore:
                    return await self._execute_issue_turn(
                        issue_data, epic, team, env, run_id, active_build, 
                        prompt_strategy_node, executor, toolbox
                    )

            await asyncio.gather(*(semaphore_wrapper(c) for c in candidates))

        if iteration_count >= max_iterations:
            final_backlog = await self.async_cards.get_by_build(active_build)
            if not self.loop_policy_node.is_backlog_done(final_backlog):
                raise ExecutionFailed(f"Hyper-Loop exhausted iterations ({max_iterations})")

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
        toolbox: ToolBox
    ):
        """Executes a single turn for one issue."""
        issue = IssueConfig.model_validate(issue_data.model_dump())
        is_review_turn = issue.status == CardStatus.CODE_REVIEW
        
        # RUN EMPIRICAL VERIFICATION (FIT) for review turns
        if is_review_turn:
            verification_result = await self.verify_issue(issue.id)
            v_msg = f"EMPIRICAL VERIFICATION RESULT: {verification_result.passed}/{verification_result.total_scenarios} Passed."
            self.notes.add(Note(from_role="system", content=v_msg, step_index=len(self.transcript)))

        # Select Seat via router decision node
        seat_name = self.router_node.route(issue, team, is_review_turn)

        seat_obj = team.seats.get(sanitize_name(seat_name))
        if not seat_obj:
            await self.async_cards.update_status(issue.id, CardStatus.CANCELED)
            return

        turn_status = CardStatus.IN_PROGRESS if not is_review_turn else CardStatus.CODE_REVIEW
        await self.async_cards.update_status(issue.id, turn_status, assignee=seat_name)

        # Prepare Role & Model
        roles_to_load = list(seat_obj.roles)
        if is_review_turn and "integrity_guard" not in roles_to_load:
            roles_to_load = ["integrity_guard"] + roles_to_load

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
        )

        print(f"  [ORCHESTRATOR] {seat_name} -> {issue.id} ({issue.status.value})")
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
            if success_eval.get("trigger_sandbox"):
                await self._trigger_sandbox(epic)
                if success_eval.get("promote_code_review"):
                    await self.async_cards.update_status(issue.id, CardStatus.CODE_REVIEW)
            
            await provider.clear_context()
            await self._save_checkpoint(run_id, epic, team, env, active_build)
        else:
            await self._handle_failure(issue, result, run_id, roles_to_load)

    def _build_turn_context(
        self,
        run_id: str,
        issue: IssueConfig,
        seat_name: str,
        roles_to_load: List[str],
        turn_status: CardStatus,
    ) -> Dict[str, Any]:
        return {
            "session_id": run_id,
            "issue_id": issue.id,
            "workspace": str(self.workspace),
            "role": seat_name,
            "roles": roles_to_load,
            "current_status": turn_status.value,
            "history": self._history_context(),
        }

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
        from orket.exceptions import CatastrophicFailure

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

        # Mechanical governance violations are terminal for the issue.
        if action == "governance_violation":
            await self.async_cards.update_status(issue.id, CardStatus.BLOCKED)
            issue.status = CardStatus.BLOCKED
            await self.async_cards.save(issue.model_dump())
            raise GovernanceViolation(f"iDesign Violation: {result.error}")

        if action == "catastrophic":
            log_event("catastrophic_failure", {
                "issue_id": issue.id,
                "retry_count": issue.retry_count,
                "error": result.error
            }, self.workspace)
            await self.async_cards.update_status(issue.id, CardStatus.BLOCKED)
            await self.async_cards.save(issue.model_dump())
            
            # Catastrophic failure shuts down the session
            from orket.state import runtime_state
            task = await runtime_state.get_task(run_id)
            if task:
                cancel_result = task.cancel()
                if asyncio.iscoroutine(cancel_result):
                    await cancel_result
                
            raise CatastrophicFailure(
                f"MAX RETRIES EXCEEDED for {issue.id}. "
                f"Limit: {issue.max_retries}. Shutting down project orchestration."
            )

        if action != "retry":
            raise ExecutionFailed(f"Unexpected evaluator action '{action}' for {issue.id}")

        # Log retry and reset to READY
        log_event("retry_triggered", {
            "issue_id": issue.id,
            "retry_count": issue.retry_count,
            "max_retries": issue.max_retries,
            "error": result.error
        }, self.workspace)
        
        await self.async_cards.update_status(issue.id, CardStatus.READY)
        await self.async_cards.save(issue.model_dump())

        raise ExecutionFailed(f"Orchestration Turn Failed (Retry {issue.retry_count}/{issue.max_retries}): {result.error}")
