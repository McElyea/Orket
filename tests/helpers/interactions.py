"""Explicit application interaction composition for transport fixtures."""
from pathlib import Path

from orket.application.interactions.commit import CommitOrchestrator
from orket.application.interactions.manager import InteractionManager
from orket.streaming.bus import StreamBus


def create_interaction_manager(root: Path) -> InteractionManager:
    return InteractionManager(bus=StreamBus(), commit_orchestrator=CommitOrchestrator(project_root=root),
                              project_root=root, stream_enabled=True)
