# Orket 0.7.0 — Windows architectural truth

Core **0.7.0** and standalone SDK **0.7.0** publish the completed Windows ATG-v1
remediation: owned effects and cleanup, explicit inputs, truthful completion,
bounded orchestration extraction, current typing and unchanged-floor coverage.

## Stability and scope

Windows CLI/API, bounded trusted extensions and recorded local llama.cpp library
flows retain their verified scopes. This is not whole-product or whole C/D/E
conformance. Linux/Mac, hosted Quality, live Docker sandbox acceptance, arbitrary
plugin purity, remote inference teardown and production soak are not established.
Known marshaller process ownership, grounding-residue and coverage capture limits
remain in the architectural-truth plan. No new capability is admitted.
The `BT4-FIXTURE-SYNC-RETIRE` removal originally targeted at 0.7.0 remains overdue:
existing synchronous fixture tombstones still refuse execution, and deprecated
domain exports remain. Use the async fixture verification service; this release
does not mark that removal obligation complete.

## Compatibility and required action

- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`

Install both attached wheels together:

```text
python -m pip install --upgrade orket-0.7.0-py3-none-any.whl orket_extension_sdk-0.7.0-py3-none-any.whl
python -m pip check
orket ext validate EXTENSION_ROOT --strict --json
```

When upgrading an old core that bundled the SDK, force-reinstall the exact SDK
wheel last with `--force-reinstall --no-deps` to restore sole namespace ownership.
SDK 0.7.0 is admitted only with matched core 0.7.0 on Windows. Do not overlay it on
published core 0.6.0/0.6.2 or infer future core compatibility.

Review nullable latency and explicit posture in `model_generate_response.v1` and
`agent_model_use_receipt.v2`. New agent declarations require the v2 host feature;
older handshakes refuse before inference. Historical v1 receipts stay readable.
Direct Python embeddings must use the current explicit input and async lifetime
contracts. Existing `python main.py` and hidden `--rock` remain deprecated but
supported through 0.7.x; new callers use `orket runtime --card`.

The proof report identifies fresh release-artifact checks and separately reused
ATG observations. Attached wheels/sdists are the exact accepted bytes; checksums
accompany them. This is GitHub asset publication, not a PyPI upload.
