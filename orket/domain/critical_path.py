from typing import List, Dict, Set
from orket.schema import EpicConfig, CardStatus

class CriticalPathEngine:
    """
    Analyzes dependencies within an Epic to identify the 'Longest Pole'.
    Uses blocking-weight to prioritize execution.
    """
    
    @staticmethod
    def get_priority_queue(epic: EpicConfig) -> List[str]:
        """
        Returns a list of Issue IDs sorted by combined priority score.
        Score = base_priority + critical_path_weight

        High Score = High priority card that blocks many other tasks.
        """
        # 1. Build adjacency map (who depends on me?)
        blocked_by_me: Dict[str, Set[str]] = {i.id: set() for i in epic.issues}

        for issue in epic.issues:
            for dependency_id in issue.depends_on:
                if dependency_id in blocked_by_me:
                    blocked_by_me[dependency_id].add(issue.id)

        # 2. Calculate recursive weights
        weights = {}
        for issue_id in blocked_by_me:
            weights[issue_id] = CriticalPathEngine.calculate_weight(issue_id, blocked_by_me)

        # 3. Calculate combined priority scores (base priority + dependency weight)
        def calculate_score(issue) -> float:
            return issue.priority + weights.get(issue.id, 0)

        # 4. Filter for READY issues and sort by combined score (descending)
        ready_issues = [i for i in epic.issues if i.status == CardStatus.READY]
        ready_issues.sort(key=calculate_score, reverse=True)

        return [i.id for i in ready_issues]

    @staticmethod
    def calculate_weight(issue_id: str, adj_map: Dict[str, Set[str]], visited=None) -> int:
        """Recursively counts how many issues are blocked by this one."""
        if visited is None: visited = set()
        
        weight = 0
        for blocked_id in adj_map.get(issue_id, set()):
            if blocked_id not in visited:
                visited.add(blocked_id)
                weight += 1 + CriticalPathEngine._calculate_weight(blocked_id, adj_map, visited)
        
        return weight
