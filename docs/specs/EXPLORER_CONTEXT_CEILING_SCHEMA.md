# Explorer Context Ceiling Schema

## Schema Version
`explorer.context_ceiling.v1`

## Required Fields
1. `schema_version` (string)
2. `generated_at` (ISO 8601 UTC string)
3. `execution_lane` (`ci` | `lab`)
4. `vram_profile` (`safe` | `balanced` | `stress`)
5. `hardware_fingerprint` (string)
6. `model_id` (string)
7. `quant_tag` (string)
8. `provenance` (object)
9. `thresholds` (object)
10. `safe_context_ceiling` (number or null)
11. `recommendation` (string)
12. `points` (array)

## Point Row Fields
1. `context` (integer)
2. `adherence_score` (number)
3. `degradation_from_baseline` (number)
4. `ttft_ms` (number or null)
5. `decode_tps` (number or null)
6. `valid` (boolean)
7. `passed` (boolean)
8. `reasons` (array of strings)
9. `summary_path` (string)

## Migration Notes (Toward v2)
1. Preserve `safe_context_ceiling` semantics in `v1`.
2. Additive fields (for example confidence score) may be added in `v1`.
3. Change to pass criteria semantics requires `explorer.context_ceiling.v2`.
