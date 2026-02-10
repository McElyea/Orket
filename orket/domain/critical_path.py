from typing import List, Dict, Set
from orket.schema import EpicConfig
from orket.core.critical_path import CriticalPathEngine as CoreCriticalPathEngine

class CriticalPathEngine:
    """
    Shim for the new CoreCriticalPathEngine.
    Maintains compatibility with EpicConfig while delegating logic to core.
    """
    
    @staticmethod
    def get_priority_queue(epic: EpicConfig) -> List[str]:
        """
        Returns a list of Issue IDs sorted by combined priority score.
        Delegates to core.
        """
        return CoreCriticalPathEngine.get_priority_queue(epic.issues)

    @staticmethod
    def calculate_weight(issue_id: str, adj_map: Dict[str, Set[str]], visited=None) -> int:
        """Delegates to core logic."""
        return CoreCriticalPathEngine.calculate_weight(issue_id, adj_map, visited)

    @staticmethod
    def build_dependency_graph(issues: List[Dict]) -> Dict[str, Set[str]]:
        """Delegates to core logic."""
        return CoreCriticalPathEngine.build_dependency_graph(issues)
