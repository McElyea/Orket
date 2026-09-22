"""Separate observed imports from the normative dependency verdict."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path

from scripts.governance.dependency_effects import evaluate_adapter_effects
from scripts.governance.dependency_imports import scan_dependencies
from scripts.governance.dependency_policy import DependencyPolicy


def authority_cycles(edges: list[dict], layers: dict[str, str]) -> list[dict]:
    forward = {n: set() for n in layers}
    reverse = {n: set() for n in layers}
    for row in edges:
        source, target = row["source"], row["target"]
        if source in layers and target in layers:
            forward[source].add(target)
            reverse[target].add(source)
    seen, order = set(), []
    for node in sorted(layers):
        stack = [(node, False)]
        while stack:
            current, finished = stack.pop()
            if finished:
                order.append(current)
            elif current not in seen:
                seen.add(current)
                stack.append((current, True))
                stack.extend((n, False) for n in sorted(forward[current], reverse=True) if n not in seen)
    seen, cycles = set(), []
    for node in reversed(order):
        component, stack = set(), [node]
        while stack:
            current = stack.pop()
            if current not in seen:
                seen.add(current)
                component.add(current)
                stack.extend(reverse[current] - seen)
        if len({layers[n] for n in component}) > 1:
            cycles.append({"modules": sorted(component), "layers": sorted({layers[n] for n in component})})
    return sorted(cycles, key=lambda row: row["modules"])


def evaluate_dependencies(observed: dict, policy: DependencyPolicy) -> dict:
    layers, unknown = {}, []
    names = set(observed["modules"]) | {row[k] for row in observed["edges"] for k in ("source", "target")}
    for name in sorted(names):
        try:
            layers[name] = policy.layer_for_module(name)
        except ValueError:
            unknown.append(name)
    exceptions = {(e.source, e.target): e for e in policy.exceptions}
    consumed, violations, redundant = {}, {}, set()
    layer_edges = Counter()
    for row in observed["edges"]:
        source, target = row["source"], row["target"]
        if source not in layers or target not in layers:
            continue
        layer_edges[(layers[source], layers[target])] += 1
        pair = source, target
        if policy.permits(source, target):
            if pair in exceptions:
                redundant.add(exceptions[pair].id)
        elif pair in exceptions:
            consumed[exceptions[pair].id] = asdict(exceptions[pair])
        else:
            violations.setdefault(pair, []).append({k: row[k] for k in ("path", "line", "kind")})
    unused = sorted(e.id for e in policy.exceptions if e.id not in consumed)
    cycles = authority_cycles(observed["edges"], layers)
    verdict = {
        "ok": not (unknown or violations or observed["analysis_errors"] or cycles or unused),
        "unknown_modules": unknown,
        "violations": [{"source": s, "target": t, "sites": sites} for (s, t), sites in sorted(violations.items())],
        "authority_cycles": cycles,
        "analysis_errors": observed["analysis_errors"],
        "exceptions": {"consumed": list(consumed.values()), "unused": unused, "redundant": sorted(redundant)},
    }
    return {
        "observed": {
            **observed,
            "layers": layers,
            "layer_edges": [{"source": s, "target": t, "count": n} for (s, t), n in sorted(layer_edges.items())],
        },
        "verdict": verdict,
    }


def analyze_repository(root: Path, policy: DependencyPolicy) -> dict:
    observed = scan_dependencies(root)
    result = evaluate_dependencies(observed, policy)
    effects = evaluate_adapter_effects(observed, policy)
    result["observed"]["adapter_effects"] = effects["modules"]
    result["verdict"]["adapter_effect_violations"] = effects["violations"]
    result["verdict"]["ok"] = result["verdict"]["ok"] and not effects["violations"]
    return result
