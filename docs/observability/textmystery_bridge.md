# TextMystery Bridge Runbook

This bridge keeps TextMystery and Orket separated while allowing contract-based integration.

## Workload
- extension id: `textmystery.bridge.extension`
- workload id: `textmystery_bridge_v1`

## Register/Refresh Bridge
Run from Orket root:

```powershell
python scripts/register_textmystery_bridge_extension.py
```

## Easiest One-Command Run
From Orket root:

```powershell
python scripts/run_textmystery_easy_smoke.py
```

If TextMystery is not at the default location, pass:

```powershell
python scripts/run_textmystery_easy_smoke.py --textmystery-root <path-to-TextMystery>
```

The smoke path runs direct local contract calls through SDK workload execution; no HTTP server is required.

This writes:
- SDK manifest under `workspace/live_ext/textmystery_bridge/extension.yaml`
- extension module under `workspace/live_ext/textmystery_bridge`
- extension catalog entry under `.orket/durable/config/extensions_catalog.json`

## Run Bridge Workload
```powershell
python scripts/run_textmystery_bridge_workload.py --operation parity-check --textmystery-root C:/Source/Orket-Extensions/TextMystery --payload-file <payload.json>
```

or

```powershell
python scripts/run_textmystery_bridge_workload.py --operation leak-check --textmystery-root C:/Source/Orket-Extensions/TextMystery --payload-file <payload.json>
```

## Local Contract Expectations
Bridge workload imports TextMystery local contract functions from:
- `<textmystery_root>/src/textmystery/interfaces/live_contract.py`

Contract details are documented in TextMystery:
- `C:\Source\Orket-Extensions\TextMystery\docs\engine\live-endpoint-contract.md`
