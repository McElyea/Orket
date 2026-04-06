
from orket.core.critical_path import CriticalPathEngine as CoreCriticalPathEngine
from orket.schema import EpicConfig


class CriticalPathEngine:
    """
    Shim for the new CoreCriticalPathEngine.
    Maintains compatibility with EpicConfig while delegating logic to core.
    """

    @staticmethod
    def get_priority_queue(epic: EpicConfig) -> list[str]:
        """
        Returns a list of Issue IDs sorted by combined priority score.
        Delegates to core.
        """
        return CoreCriticalPathEngine.get_priority_queue(epic.issues)

    @staticmethod
    def calculate_weight(issue_id: str, adj_map: dict[str, set[str]], visited=None) -> int:
        """Delegates to core logic."""
        return CoreCriticalPathEngine.calculate_weight(issue_id, adj_map, visited)

    @staticmethod
    def build_dependency_graph(issues: list[dict]) -> dict[str, set[str]]:
        """Delegates to core logic."""
        return CoreCriticalPathEngine.build_dependency_graph(issues)
