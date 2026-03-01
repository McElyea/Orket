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

This writes:
- SDK manifest under `workspace/live_ext/textmystery_bridge/extension.yaml`
- extension module under `workspace/live_ext/textmystery_bridge`
- extension catalog entry under `.orket/durable/config/extensions_catalog.json`

## Run Bridge Workload
```powershell
python scripts/run_textmystery_bridge_workload.py --operation parity-check --endpoint-base-url http://127.0.0.1:8787 --payload-file <payload.json>
```

or

```powershell
python scripts/run_textmystery_bridge_workload.py --operation leak-check --endpoint-base-url http://127.0.0.1:8787 --payload-file <payload.json>
```

## Endpoint Expectations
TextMystery side should expose:
- `POST /textmystery/parity-check`
- `POST /textmystery/leak-check`

Contract details are documented in TextMystery:
- `C:\Source\Orket-Extensions\TextMystery\docs\engine\live-endpoint-contract.md`
