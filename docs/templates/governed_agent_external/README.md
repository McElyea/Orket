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

Use the SDK version required by the selected core distribution. Keep its matching
core/SDK candidate pair together; the template does not grant compatibility with
an older host. Model latency can be unavailable; token usage and response status
are separate. The host's `orket demo local-agent --project <directory>` prepares
this template and the shared ticket inputs for a bounded actual-provider example.
