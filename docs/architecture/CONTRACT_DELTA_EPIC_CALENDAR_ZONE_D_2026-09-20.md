# Epic calendar timezone regression correction

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version: 0.6.53 candidate, 2026-09-20.
- Durable contract: `docs/specs/REMAINING_RUNTIME_INPUTS.md`.

## Correction
Version 0.6.52 incorrectly converted the selected UTC observation to the host
timezone. The prior helper uses `ORKET_TIMEZONE`, defaulting to UTC. Near week
boundaries the new path could therefore publish a different sprint. Its parity
fixture covered the pure calculation over already converted dates and did not
verify runtime timezone selection. The .52 proof and failed .53 probes are retained.

Owner construction now captures the timezone name with the EOS baseline from the
same environment snapshot. An explicit construction environment, including an
empty one, is authoritative. Direct orchestrator construction accepts
`calendar_timezone_name`, defaulting to UTC. Existing MST normalization and unknown
zone fallback remain owned by `time_utils.configured_timezone`.

Setup captures UTC before its first await. The existing timezone resolver executes
in an owned worker because IANA resolution can read timezone data. Its result is
applied to the captured instant before asset reads and card publication. Repeated
cancellation and timeout retain the worker until completion; a worker error takes
precedence over cancellation. This is not a universal bound on OS timezone reads.

Existing stored sprint values are retained. No automatic migration of .52-created
cards or historical evidence is attempted. Recovery authority is unchanged.

## Verification and rollback
Use independently captured published .51 timezone/calculation outcomes, actual
asset and SQLite paths, environment/clock rotation, and owned worker interruption
checks. Keep the D1 0.5-second responsiveness bound. Controlled clocks and providers
do not prove inference or wall-clock stability. Rollback preserves records and
must acknowledge the .52 timezone defect rather than declare that behavior parity.

## Versioning decision
- Patch bug fix restoring configured calendar behavior; no required caller migration.
- Direct owners can supply an explicit timezone name; the default remains UTC.
- Remaining D/E/CAP and explicit lane acceptance remain open.
