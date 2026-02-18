# Benchmark Determinism Profiles

This document defines expected deterministic behavior for benchmark task profiles and the allowed exception boundaries.

## Profiles
1. `strict`
   - Repeated runs must produce identical pass/fail outcomes and identical normalized artifacts.
   - Hash drift is not allowed.
2. `bounded`
   - Repeated runs must preserve outcome correctness while allowing bounded runtime variance.
   - Minor timing variation is allowed; semantic artifact drift is not.
3. `convergence`
   - Repeated runs may vary early, but must converge to stable pass conditions within bounded attempts.
   - Convergence metrics must be recorded (`attempts_to_pass`, `drift_rate`).

## Allowed Exceptions
1. Timestamp and absolute path differences are normalized by the harness and are not treated as drift.
2. Runtime latency variation is allowed for `bounded` and `convergence` profiles when correctness remains stable.
3. Retry-path differences are allowed only when final artifacts satisfy the acceptance contract.

## Fault-Injection Baseline
Tier-3 crash-sensitive tasks include the following required scenarios:
1. `timeout`
2. `partial_write`
3. `malformed_input`
4. `interrupted_run`
5. `retry_path`
