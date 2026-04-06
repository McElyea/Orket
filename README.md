# Orket

Orket is a local-first workflow runtime for card-based execution with persistent state, tool gating, and multiple operator surfaces.

This README is intentionally narrow. It describes the repo entrypoints and current truths only.

## Current Repo Truth

- Default runtime entrypoint: `python main.py`
- Named card runtime entrypoint: `python main.py --card <card_id>`
- API runtime entrypoint: `python server.py`
- Canonical test command: `python -m pytest -q`
- Active docs index: [docs/README.md](docs/README.md)
- Active roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Current high-impact authority snapshot: [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## What Exists Today

- A runtime and API for orchestration, turns, cards, and workflow state.
- Legacy CLI `--rock` remains accepted as a hidden compatibility alias to the named card runtime.
- Governed turn-tool execution with fail-closed namespace enforcement on the governed path.
- Control-plane persistence for selected live lanes, including sandbox orchestration, governed turn-tool execution, governed kernel actions, approval-gated reservation and operator flows, coordinator reservation and lease flows, and the Gitea state worker path.
- Deterministic and observability-oriented runtime artifacts under the normal workspace and durable `.orket/` paths.

## What Is Not Universally True Yet

- Control-plane authority is not universal across all admission, scheduling, workload execution, and operator surfaces.
- Effect-journal publication is not yet the default truth path for all workload and tool execution.
- Namespace and safe-tooling enforcement are stronger on the governed turn-tool path than on the rest of the runtime.
- Broader supervisor-owned checkpoint creation is still partial.

For the exact current boundary, use [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md) instead of inferring from older docs or broad product language.

## Quick Start

1. Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Optional extras:

```bash
python -m pip install -e ".[dev,vision]"
```

Use `vision` only for image-processing features; base runtime installs no longer pull Pillow.

2. Optional local environment file:

```bash
cp .env.example .env
```

3. Start the default runtime:

```bash
python main.py
```

4. Start the API server:

```bash
python server.py
```

## Verification

- Canonical test command:

```bash
python -m pytest -q
```

- Routine proof that is not explicit sandbox acceptance should set `ORKET_DISABLE_SANDBOX=1`.
- Real sandbox creation is intentionally fail-closed in the normal pytest suite. See [docs/CONTRIBUTOR.md](docs/CONTRIBUTOR.md) and [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md) for the current testing policy.

## Documentation

- Start with [docs/README.md](docs/README.md)
- Contributor workflow: [docs/CONTRIBUTOR.md](docs/CONTRIBUTOR.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Active execution priorities: [docs/ROADMAP.md](docs/ROADMAP.md)

## License

Orket is source-available, not open source, under the Business Source License 1.1 in [LICENSE](LICENSE).

Commercial uses outside the Additional Use Grant are described in [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).
