# Explorer Thermal Stability Schema

## Schema Version
`explorer.thermal_stability.v1`

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
10. `heat_soak_detected` (boolean)
11. `polluted_run_rate` (number)
12. `cooldown_failure_rate` (number)
13. `recommendation` (string)
14. `points` (array)

## Point Row Fields
1. `run_index` (integer)
2. `summary_path` (string)
3. `total_latency` (number)
4. `thermal_start_c` (number or null)
5. `thermal_end_c` (number or null)
6. `thermal_delta_c` (number or null)
7. `polluted` (boolean)
8. `cooldown_ok` (boolean)
9. `reasons` (array of strings)

## Migration Notes (Toward v2)
1. `heat_soak_detected` and `polluted_run_rate` semantics are stable in `v1`.
2. Additional trend metrics can be additive in `v1`.
3. New thermal state categories require `explorer.thermal_stability.v2`.
