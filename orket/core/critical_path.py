from typing import Any


class ImpactWeightCalculator:
    """
    Calculates dependency impact weight for task prioritization.
    Pure domain logic: no I/O, no DB access.
    """

    @staticmethod
    def get_priority_queue(issues: list[Any]) -> list[str]:
        """
        Returns a list of Issue IDs sorted by combined priority score.
        Score = base_priority + impact_weight
        """
        # 1. Build adjacency map (who depends on me?)
        adj_map = ImpactWeightCalculator.build_dependency_graph(issues)

        # 2. Calculate recursive weights
        weights: dict[str, int] = {}
        for issue in issues:
            i_id = ImpactWeightCalculator._issue_id(issue)
            weights[i_id] = ImpactWeightCalculator.calculate_weight(i_id, adj_map)

        # 3. Calculate combined priority scores (base priority + dependency weight)
        def calculate_score(issue: Any) -> float:
            i_id = ImpactWeightCalculator._issue_id(issue)
            # Handle priority if it's a string or missing
            p = issue.get("priority", 2.0) if isinstance(issue, dict) else getattr(issue, "priority", 2.0)
            if not isinstance(p, (int, float)):
                p = 2.0
            return float(p) + weights.get(i_id, 0)

        # 4. Filter for READY issues and sort by combined score (descending)
        ready_issues: list[Any] = []
        for i in issues:
            status = i.get("status") if isinstance(i, dict) else getattr(i, "status", None)
            status_value = str(getattr(status, "value", status) or "").strip().lower()
            if status_value == "ready":
                ready_issues.append(i)

        ready_issues.sort(key=calculate_score, reverse=True)

        return [ImpactWeightCalculator._issue_id(issue) for issue in ready_issues]

    @staticmethod
    def calculate_weight(issue_id: str, adj_map: dict[str, set[str]], visited: set[str] | None = None) -> int:
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
    def build_dependency_graph(issues: list[Any]) -> dict[str, set[str]]:
        """
        Builds an adjacency map where Key = Issue ID, Value = Set of Issue IDs that depend on Key.
        Input issues should be dicts or objects with 'id' and 'depends_on' (list of IDs).
        """
        adj_map: dict[str, set[str]] = {}

        for issue in issues:
            # Handle both dictionary and object access
            i_id = ImpactWeightCalculator._issue_id(issue)
            deps_raw = issue.get("depends_on", []) if isinstance(issue, dict) else getattr(issue, "depends_on", [])
            deps = deps_raw if isinstance(deps_raw, list) else []

            for dep_id_raw in deps:
                dep_id = str(dep_id_raw or "").strip()
                if not dep_id or not i_id:
                    continue
                if dep_id not in adj_map:
                    adj_map[dep_id] = set()
                adj_map[dep_id].add(i_id)

        return adj_map

    @staticmethod
    def _issue_id(issue: Any) -> str:
        identifier = issue.get("id") if isinstance(issue, dict) else getattr(issue, "id", "")
        return str(identifier or "").strip()


class CriticalPathEngine(ImpactWeightCalculator):
    """Compatibility alias for historical imports."""
