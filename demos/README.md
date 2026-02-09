# Orket Demos

Interactive demonstration scripts showing how Orket features work.

## Available Demos

### priority.py
Shows the priority-based scheduling system:
- Basic priority ordering (no dependencies)
- Priority + dependency weighting
- Realistic sprint scenarios
- Legacy string migration

```bash
python demos/priority.py
```

### wait_reason.py
Demonstrates diagnostic bottleneck detection:
- Resource constraints (VRAM maxed)
- Dependency pile-ups
- Human intervention requirements
- Mixed bottleneck scenarios
- Unblocking flows

```bash
python demos/wait_reason.py
```

## Purpose

These demos are educational tools that show how v0.3.8 features work in practice. They use real Orket classes but with simplified scenarios.
