import asyncio
import json
import uuid
import os
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
from orket.services.prompt_compiler import PromptCompiler
from orket.services.tool_gate import ToolGate
from orket.tools import ToolBox, get_tool_map
from orket.llm import LocalModelProvider
from orket.logging import log_event
from orket.exceptions import ExecutionFailed, GovernanceViolation
from orket.domain.state_machine import StateMachine
from orket.utils import sanitize_name

class AsyncModelClient:
    """Async wrapper for model providers."""
    def __init__(self, provider):
        self.provider = provider
    async def complete(self, messages):
        return await self.provider.complete(messages)

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
        self.context_window = max(1, int(os.getenv("ORKET_CONTEXT_WINDOW", "10")))

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
            except Exception as e:
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
        )
        
        # Concurrency Control (Phase 6.2)
        concurrency_limit = 3 # Can be made configurable in OrganizationConfig
        semaphore = asyncio.Semaphore(concurrency_limit)

        log_event("orchestrator_hyper_loop_start", {"epic": epic.name, "run_id": run_id, "concurrency": concurrency_limit}, self.workspace)

        iteration_count = 0
        max_iterations = 20

        while iteration_count < max_iterations:
            iteration_count += 1
            
            # 1. Identify all candidates
            # Prioritize CODE_REVIEW (serial for verification stability) + READY (parallel)
            backlog = await self.async_cards.get_by_build(active_build)
            in_review = [i for i in backlog if i.status == CardStatus.CODE_REVIEW]
            
            # Get issues whose dependencies are met
            independent_ready = await self.async_cards.get_independent_ready_issues(active_build)
            
            if target_issue_id:
                # Target mode: Only run the target if it's ready/review
                target = next((i for i in backlog if i.id == target_issue_id), None)
                if not target: break
                if target.status == CardStatus.CODE_REVIEW:
                    candidates = [target]
                elif target.status == CardStatus.READY and any(i.id == target_issue_id for i in independent_ready):
                    candidates = [target]
                else:
                    candidates = [] # Target not ready yet
            else:
                candidates = in_review + independent_ready

            if not candidates:
                # Check if we are actually done or just blocked
                is_done = all(i.status in [CardStatus.DONE, CardStatus.CANCELED] for i in backlog)
                if is_done:
                    print(f"  [ORCHESTRATOR] Epic '{epic.name}' complete.")
                break
            
            print(f"  [TICK] Running {len(candidates)} tasks in parallel...")

            # 2. Parallel Dispatch with Semaphore
            async def semaphore_wrapper(issue_data):
                async with semaphore:
                    return await self._execute_issue_turn(
                        issue_data, epic, team, env, run_id, active_build, 
                        model_selector, executor, toolbox
                    )

            await asyncio.gather(*(semaphore_wrapper(c) for c in candidates))

        if iteration_count >= max_iterations:
             raise ExecutionFailed(f"Hyper-Loop exhausted iterations ({max_iterations})")

    async def _execute_issue_turn(
        self, 
        issue_data: Any, 
        epic: EpicConfig, 
        team: TeamConfig, 
        env: EnvironmentConfig, 
        run_id: str, 
        active_build: str,
        model_selector: ModelSelector,
        executor: TurnExecutor,
        toolbox: ToolBox
    ):
        """Executes a single turn for one issue."""
        issue = IssueConfig.model_validate(issue_data.model_dump())
        is_review_turn = issue.status == CardStatus.CODE_REVIEW
        
        # Select Seat & Role
        seat_name = issue.seat
        if is_review_turn:
            # RUN EMPIRICAL VERIFICATION (FIT)
            verification_result = await self.verify_issue(issue.id)
            v_msg = f"EMPIRICAL VERIFICATION RESULT: {verification_result.passed}/{verification_result.total_scenarios} Passed."
            self.notes.add(Note(from_role="system", content=v_msg, step_index=len(self.transcript)))
            
            verifier_seat = next((name for name, s in team.seats.items() if "integrity_guard" in s.roles), None)
            if verifier_seat: seat_name = verifier_seat

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
        selected_model = model_selector.select(role=roles_to_load[0], asset_config=epic)
        dialect_name = model_selector.get_dialect_name(selected_model)
        dialect = self.loader.load_asset("dialects", dialect_name, DialectConfig)
        
        provider = LocalModelProvider(model=selected_model, temperature=env.temperature, timeout=env.timeout)
        client = AsyncModelClient(provider)

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

        context = {
            "session_id": run_id,
            "issue_id": issue.id,
            "workspace": str(self.workspace),
            "role": seat_name,
            "roles": roles_to_load,
            "current_status": turn_status.value,
            "history": self._history_context()
        }

        print(f"  [ORCHESTRATOR] {seat_name} -> {issue.id} ({issue.status.value})")
        result = await executor.execute_turn(issue, role_config, client, toolbox, context, system_prompt=system_desc)

        if result.success:
            self.transcript.append(result.turn)
            updated_issue = await self.async_cards.get_by_id(issue.id)
            
            # Record significant turns in memory
            if "decision" in result.turn.content.lower() or "architect" in seat_name:
                await self.memory.remember(
                    content=f"Decision by {seat_name} on {issue.id}: {result.turn.content[:200]}...",
                    metadata={"issue_id": issue.id, "role": seat_name, "type": "decision"}
                )
            
            # Sandbox triggering
            if (updated_issue.status == CardStatus.CODE_REVIEW or 
                (updated_issue.status == issue.status and not is_review_turn)):
                await self._trigger_sandbox(epic)
                if updated_issue.status == issue.status:
                    await self.async_cards.update_status(issue.id, CardStatus.CODE_REVIEW)
            
            await provider.clear_context()
            await self._save_checkpoint(run_id, epic, team, env, active_build)
        else:
            await self._handle_failure(issue, result, run_id, roles_to_load)

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

        # Mechanical governance violations are terminal for the issue.
        if result.violations:
            await self.async_cards.update_status(issue.id, CardStatus.BLOCKED)
            issue.status = CardStatus.BLOCKED
            await self.async_cards.save(issue.model_dump())
            raise GovernanceViolation(f"iDesign Violation: {result.error}")
        
        issue.retry_count += 1
        
        if issue.retry_count > issue.max_retries:
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
