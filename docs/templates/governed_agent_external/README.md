# Governed Agent Extension Starter

This template implements one bounded async iteration through public
`orket_extension_sdk` types. Planner, actor, and critic are sequential stages
inside one workload; they do not own scheduling, effects, provider credentials,
or completion truth.

Install a development SDK wheel in an isolated extension environment, then run:

```bash
python -m pip install <path-to-sdk-wheel> -e ".[dev]"
python -m orket_extension_sdk.validate . --strict --with-import-scan --json
python -m pytest -q
```

The SDK validation command proves author conformance only. A host that has not
admitted `governed_agent_loop.v1`, `agent_stdio_ipc.v1`, and
`agent_model_use_receipt.v2` must refuse this
extension before child startup.

This template targets the paired SDK `0.7.0a1`/architectural-truth host candidate.
Model latency can be unavailable; token usage and response status are separate.
Published core 0.6.0/0.6.2 artifacts require their original SDK 0.6.0 pair.
