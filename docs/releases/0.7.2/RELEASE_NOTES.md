# Orket 0.7.2 — installed Windows reliability

Date: 2026-10-04

Fresh default installs now include the WebSocket transport used by the interaction
API. Disconnected interaction sockets release their requests so graceful shutdown
can complete. Response parsing preserves prose word boundaries, allowing the
existing strict-grounding rule to reject speculative text before tool dispatch.

Core pins the separately packaged SDK exactly to 0.7.2. The SDK increment records
the tested pair and packaging identity; its public behavior is unchanged.

- `compatibility_status`: `preserved`
- `affected_audience`: `all`
- `migration_requirement`: `none`

Install both release wheels together and run `python -m pip check`. No source or
schema migration is required. Strict-grounding callers may now receive the
already-defined corrective retry/refusal for prose the defective parser admitted.
Do not suppress a missing-board startup warning; initialize or restore valid
project assets as described in the [operator walkthrough](OPERATOR_WALKTHROUGH.md).

Stability: this remains an early local runtime. Fresh evidence covers native
Windows Python 3.11.14/3.12.2, actual llama.cpp interaction completion/cancellation,
durable lifecycle inspection, local cleanup, parser/validator integration and
matched SDK validation. It does not certify arbitrary model output, remote
inference termination, other platforms, hosted CI, or general card execution.
The initial embedded template failed the separately declared card-profile check.
Before publication, an independently replaced server used the declared template;
fresh bounded TurnExecutor file-write and grounding checks then passed on both
interpreters. No task command restarted either server or bypassed its guard.

See the [proof report](PROOF_REPORT.md), [contract delta](../../architecture/CONTRACT_DELTA_PRR_RELIABILITY_2026-10-04.md),
and [exact file inventory](FILES_TOUCHED.md). Previous 0.7.0/0.7.1 tags and assets
remain unchanged. Distribution is GitHub release assets; no PyPI upload is claimed.
