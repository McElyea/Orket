# Governed Run Demo

Run:

```bash
orket demo governed-run
```

This writes:

- `.runs/governed-run-demo/evidence.json`
- `.runs/governed-run-demo/transcript.md`
- `.runs/governed-run-demo/replay.json`
- `.runs/governed-run-demo/summary.md`

Equivalent scenario command:

```bash
orket run scenario examples/governed-run/scenario.yaml
```

Inspect and replay:

```bash
orket inspect .runs/governed-run-demo
orket replay .runs/governed-run-demo
```

What it proves: a simulated model proposes actions, Orket classifies risk, allows a read-only observation, gates or blocks risky side effects, writes evidence, and reconstructs decisions from evidence without rerunning unsafe effects.

What it does not prove: provider behavior, continuous agents, production safety, or broad autonomous execution.
