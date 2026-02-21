# Explorer Frontier Schema

## Schema Version
`explorer.frontier.v1`

## Required Fields
1. `schema_version` (string)
2. `generated_at` (ISO 8601 UTC string)
3. `execution_lane` (`ci` | `lab`)
4. `vram_profile` (`safe` | `balanced` | `stress`)
5. `hardware_fingerprint` (string)
6. `model_id` (string)
7. `quant_tag` (string)
8. `provenance` (object)
9. `sessions` (array)

## Session Row Fields
1. `model_id` (string)
2. `baseline_quant` (string)
3. `minimum_viable_quant` (string)
4. `best_value_quant` (string)
5. `recommendation` (string)
6. `quant_rows` (array of quant metric rows)

## Migration Notes (Toward v2)
1. Keep existing required fields unchanged.
2. Additive fields allowed (for example utility-score breakdown) without changing `v1`.
3. If required fields or semantics change, create `explorer.frontier.v2`.
