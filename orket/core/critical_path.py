from typing import Dict, Any, Set, List

class CriticalPathEngine:
    """
    Calculates the critical path (longest dependency chain) for a set of tasks.
    Pure domain logic: No I/O, no DB access.
    """
    
    @staticmethod
    def get_priority_queue(issues: List[Any]) -> List[str]:
        """
        Returns a list of Issue IDs sorted by combined priority score.
        Score = base_priority + critical_path_weight
        """
        # 1. Build adjacency map (who depends on me?)
        adj_map = CriticalPathEngine.build_dependency_graph(issues)

        # 2. Calculate recursive weights
        weights = {}
        for issue in issues:
            i_id = issue.get("id") if isinstance(issue, dict) else issue.id
            weights[i_id] = CriticalPathEngine.calculate_weight(i_id, adj_map)
        
        # 3. Calculate combined priority scores (base priority + dependency weight)
        def calculate_score(issue) -> float:
            i_id = issue.get("id") if isinstance(issue, dict) else issue.id
            # Handle priority if it's a string or missing
            p = issue.get("priority", 2.0) if isinstance(issue, dict) else getattr(issue, "priority", 2.0)
            if isinstance(p, str): p = 2.0 # Default if not yet converted
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
    def calculate_weight(issue_id: str, adj_map: Dict[str, Set[str]], visited: Set[str] = None) -> int:
        """
        Recursively calculates the weight of an issue based on its dependency chain length.
        Weight = 1 + max(weight(dependencies))
        """
        if visited is None:
            visited = set()
            
        weight = 0
        # For each task that depends on this issue_id (reverse dependency graph)
        # We need to know who is blocked by issue_id.
        # But wait, standard critical path is usually forward dependencies.
        # Let's verify the logic: A task is critical if MANY things depend on it.
        # So we want to know the depth of the dependency tree rooted at this task.
        
        # The adj_map passed here seems to be: Key = Issue, Value = Set of issues BLOCKED BY Key
        
        for blocked_id in adj_map.get(issue_id, set()):
            if blocked_id not in visited:
                visited.add(blocked_id)
                # Recurse: Weight is 1 (for this node) + max path of children
                # Actually, this logic sums the weights? No, let's look at the original code.
                # The original code was: weight += 1 + recursive_call
                # That sums the entire subgraph size, which is a proxy for "Impact".
                # True critical path length would use max(), but "Total Impact" uses sum().
                # Given "Priority" context, impact (how many things I block) is a good metric.
                weight += 1 + CriticalPathEngine.calculate_weight(blocked_id, adj_map, visited)
        
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
