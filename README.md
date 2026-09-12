# Orket

Orket is an early local-first runtime for governing AI agent side effects.

The core idea is simple: a model can propose an action, but Orket controls whether that action is allowed, approved, executed, and recorded.

The first demo shows a mock local model proposing a file write. Orket pauses for operator approval, writes the file only if approved, and emits a hash-chained JSONL ledger that can be verified afterward.

## Try the governed-action demo

No network, Ollama, GPU, or `.env` file is required.

```bash
python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"
orket-quickstart
python -m orket.quickstart.verify_ledger <ledger>
```

The demo prints the exact `<ledger>` path to use in the verifier command.
For a noninteractive run, supply the decision explicitly:

```bash
orket-quickstart --decision deny
orket-quickstart --decision approve --workspace <directory>
```

If interactive input is unavailable, the command exits nonzero with
`E_QUICKSTART_INPUT_REQUIRED` instead of printing a traceback.

You should see the governance boundary in the terminal:

```text
GOVERNED ACTION REQUEST
tool: write_file
path: quickstart_out/hello_from_orket.txt
status: waiting_for_operator
Approve this action? [a]pprove / [d]eny:
```

If you approve, Orket writes `quickstart_out/hello_from_orket.txt` and records the effect. If you deny or enter anything else, the file is not written and the ledger records why the effect was skipped.

## What this proves

- A model proposal is not treated as execution authority.
- The operator sees the proposed side effect before it happens.
- The side effect happens only on approval.
- The run emits a hash-chained JSONL ledger.
- The verifier fails if ledger content, ordering, sequence, previous hash, or event hash is changed.

## Claim limits

This is an early project. The quickstart uses a mock local model so the governance loop can be tested without setup tax.

The demo proves the local approval gate, file side effect, and ledger verification path for one governed action. It does not prove broad autonomous-agent safety, production readiness, model quality, replay determinism, or text determinism.

For broader compatibility and migration boundaries, use [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) instead of inferring from older docs or broad product language.

## Current Repo Truth

- Governed-action demo entrypoint: `orket-quickstart` or `python -m orket.quickstart.governed_action_demo`
- Governed-run deterministic demo: `orket demo governed-run` using its packaged default; custom scenario path: `orket run scenario examples/governed-run/scenario.yaml`
- Governed-run inspection and replay: `orket inspect .runs/<run_id>` and `orket replay .runs/<run_id>`
- Governed-agent path: bounded CLI submission and durable manual wake enqueue/list/inspect/cancel/recover/actions remain under `orket agent`; authenticated API wake, schedule, and HMAC webhook admission plus controls and inspection are under `/v1/agent-wakes`, `/v1/agent-schedules`, `/v1/agent-webhooks`, `/v1/agent-runs`, and `/v1/agent-runtime/status`. API-owned continuous dispatch is disabled by default and requires explicit `ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED=1` provider configuration. llama.cpp is the default provider across local runtime and testing entrypoints. Live Qwen3.8 CLI/API continuation and approval/denial across restart are proven for the bounded reference workload; general coding-objective verification remains outside that proof.
- Default runtime entrypoint: `orket runtime`
- Named card runtime entrypoint: `orket runtime --card <card_id>`
- API runtime entrypoint: `python server.py`
- Canonical test command: `python -m pytest -q`
- Active docs index: [docs/README.md](docs/README.md)
- Active roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Current high-impact authority snapshot: [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## What Exists Today

- A runtime and API for orchestration, turns, cards, and workflow state.
- Governed turn-tool execution with fail-closed namespace enforcement on the governed path.
- Control-plane persistence for selected live lanes, including sandbox orchestration, governed turn-tool execution, governed kernel actions, cards epic execution, manual review-run execution, extension workload execution, approval-gated reservation and operator flows, coordinator reservation and lease flows, and the Gitea state worker path.
- Deterministic and observability-oriented runtime artifacts under the normal workspace and durable `.orket/` paths.
- Source wrapper `python main.py [runtime arguments]` remains supported through `0.6.x`.
- Legacy runtime `--rock` remains accepted as a hidden compatibility alias to the named card runtime; new callers use `--card`.

## Bounded Proof Slice

Orket currently ships one proof-backed external trust slice for `trusted_repo_config_change_v1`.

- Current truthful claim ceiling for that slice: `verdict_deterministic`
- Current posture: proof-only and fixture-bounded
- Not yet proven for that slice: replay determinism and text determinism

The practical trust reason for that slice is that Orket can package approval, effect, validator, final-truth, and claim-tier evidence into a witness bundle and refuse stronger claims when that evidence is missing.

Use [docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md](docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md) for the evaluator path and [docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md](docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md) for the publication boundary.

## Full Runtime Quick Start

1. Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev]"
```

Optional extras:

```bash
python -m pip install -e "./orket_extension_sdk[testing]" -e ".[dev,vision]"
```

Use `vision` only for image-processing features; base runtime installs no longer pull Pillow.

2. Optional local environment file:

```bash
cp .env.example .env
```

The API runtime entrypoint loads this repo-local `.env` before app construction. Explicit environment variables already set in the launching shell still take precedence.

3. Start the default runtime:

```bash
orket runtime
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
