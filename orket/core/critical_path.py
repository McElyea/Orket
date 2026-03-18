from typing import Any, Dict, List, Set


class ImpactWeightCalculator:
    """
    Calculates dependency impact weight for task prioritization.
    Pure domain logic: no I/O, no DB access.
    """

    @staticmethod
    def get_priority_queue(issues: List[Any]) -> List[str]:
        """
        Returns a list of Issue IDs sorted by combined priority score.
        Score = base_priority + impact_weight
        """
        # 1. Build adjacency map (who depends on me?)
        adj_map = ImpactWeightCalculator.build_dependency_graph(issues)

        # 2. Calculate recursive weights
        weights = {}
        for issue in issues:
            i_id = issue.get("id") if isinstance(issue, dict) else issue.id
            weights[i_id] = ImpactWeightCalculator.calculate_weight(i_id, adj_map)

        # 3. Calculate combined priority scores (base priority + dependency weight)
        def calculate_score(issue) -> float:
            i_id = issue.get("id") if isinstance(issue, dict) else issue.id
            # Handle priority if it's a string or missing
            p = issue.get("priority", 2.0) if isinstance(issue, dict) else getattr(issue, "priority", 2.0)
            if isinstance(p, str):
                p = 2.0  # Default if not yet converted
            return p + weights.get(i_id, 0)

        # 4. Filter for READY issues and sort by combined score (descending)
        ready_issues = []
        for i in issues:
            status = i.get("status") if isinstance(i, dict) else getattr(i, "status", None)
            if status == "ready" or (hasattr(status, "value") and status.value == "ready"):
                ready_issues.append(i)

        ready_issues.sort(key=calculate_score, reverse=True)

        return [issue.get("id") if isinstance(issue, dict) else issue.id for issue in ready_issues]

    @staticmethod
    def calculate_weight(issue_id: str, adj_map: Dict[str, Set[str]], visited: Set[str] | None = None) -> int:
        """
        Recursively calculates the impact weight of an issue based on blocked descendants.
        Weight = sum(1 + weight(blocked_child)) for each blocked child.
        """
        if visited is None:
            visited = set()

        weight = 0
        for blocked_id in adj_map.get(issue_id, set()):
            if blocked_id in visited:
                continue
            # Branch-local visited prevents sibling branches from incorrectly sharing state.
            next_visited = set(visited)
            next_visited.add(blocked_id)
            weight += 1 + ImpactWeightCalculator.calculate_weight(blocked_id, adj_map, next_visited)

        return weight

    @staticmethod
    def build_dependency_graph(issues: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """
        Builds an adjacency map where Key = Issue ID, Value = Set of Issue IDs that depend on Key.
        Input issues should be dicts or objects with 'id' and 'depends_on' (list of IDs).
        """
        adj_map: Dict[str, Set[str]] = {}

        for issue in issues:
            # Handle both dictionary and object access
            i_id = issue.get("id") if isinstance(issue, dict) else issue.id
            deps = issue.get("depends_on", []) if isinstance(issue, dict) else getattr(issue, "depends_on", [])

            for dep_id in deps:
                if dep_id not in adj_map:
                    adj_map[dep_id] = set()
                adj_map[dep_id].add(i_id)

        return adj_map


class CriticalPathEngine(ImpactWeightCalculator):
    """Compatibility alias for historical imports."""
