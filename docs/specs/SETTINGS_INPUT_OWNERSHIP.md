# Settings input ownership

Owner: Orket Core
Last updated: 2026-09-21
Status: Active contract

## Inputs and selection

`orket.settings` is the application entrypoint. `UserSettingsService` owns file
read/publication and migration policy; the settings file adapter performs its
authorized effects and declares `side_effecting = True`.

Each async operation captures invocation directory, `ORKET_DURABLE_ROOT`, explicit
settings/preferences path selections, and supplied JSON values before its first
await. Path resolution and all filesystem effects execute in the owned worker.
Defaults remain `.orket/durable/config/user_settings.json` and `preferences.json`
under the captured invocation directory. Explicit setters select absolute paths
without reading files and invalidate the corresponding runtime snapshot in the
calling context. Configure these process-wide overrides before concurrent use;
they are not per-application configuration isolation. Application integrations
needing separate owners can supply a distinct `SettingsLocation` to the service.

There is no implicit persistent-data or default-path cache. Unbound reads observe
the selected files again. Default locations follow a new invocation directory or
durable-root input on a subsequent operation. Already admitted work retains its
original location. Filesystem aliases and external path replacement are not an
OS containment or hostile-editor boundary.

## Runtime snapshots and synchronous admission

`set_runtime_settings_context` serializes supplied nested JSON objects before
binding either snapshot. Getters deserialize detached dictionaries. Child tasks
inherit values through context variables; callers cannot mutate another reader's
snapshot by modifying input or exported objects. `get_setting` observes the
environment captured with that context. Rebinding is explicit input rotation.

Synchronous getters use a bound snapshot or a pre-loop bootstrap bridge. A cold
read in an active event loop raises `SettingsBridgeError` before filesystem
probing, even when no settings file exists. `load_user_settings_async` and
`load_user_preferences_async` observe persistence and do not overwrite the
caller's explicit runtime snapshots. Saves likewise do not
silently rotate active runtime inputs. The historical bridge warning that
`asyncio.run` loses context is removed; it propagates caller context.

The admin API settings and runtime-policy routes await persistence APIs directly.
They display stored inputs independently of bound runtime snapshots and retain
the admitted file worker through request cancellation and application shutdown.
The router retains the stored object used for validation and supplies it as the
expected value when saving. Under native writer ownership, the service compares
the current and expected JSON objects before publication. A changed object or
busy cooperating writer returns HTTP 409 with `settings_conflict`; reload before
retrying. This prevents one admitted admin update from silently overwriting
another. It is a value comparison, not a revision history or protection against
noncooperating editors. Direct callers may pass `expected` to settings saves;
unconditional full-object saves retain explicit replacement semantics.

`load_env` is an explicit synchronous bootstrap step and is idempotent after its
first successful load. Neither persistence nor dotenv loading has pytest-specific
behavior. Tests explicitly select temporary paths and bootstrap state.

CLI startup awaits persisted preferences and settings after onboarding, then
explicitly binds both snapshots in its calling task before constructing runtime
components. Cold synchronous application construction from an async embedding
must run in an owned worker or receive explicitly bound settings first.

`capture_runtime_settings_async` collects inputs for asynchronous runtime
construction. Settings and preferences independently retain their bound JSON
snapshot when present; unbound values use the settings service at a location
captured before the first await. An empty bound object is authoritative. The
collector returns detached values without rotating the caller's context. It
retains the admitted worker, including selected preference migration, through
cancellation; interruption does not imply rollback. Existing malformed-data,
ownership and migration refusals remain visible. This is not an atomic snapshot
across independent file reads. `RuntimeConstructionInputs.capture_async` retains
the invocation root and environment before that collection begins.

## File effects and interruption

Only a missing file yields an empty settings object. Invalid JSON, duplicate
keys, non-finite numbers (including exponent overflow), non-object payloads and observation failures refuse;
they cannot silently select default policy. Writes serialize detached input,
flush a same-directory temporary file, replace the target and verify its bytes.
Each admitted worker settles, including lock release and temporary-file cleanup,
before cancellation returns. Worker failure takes precedence over cancellation.
An interrupted save can have committed; callers inspect persistence before retry.

Cooperating mutations acquire the existing host-native nonblocking file locks for
their selected settings/preferences paths, in sorted order. An actual legacy
migration additionally owns the legacy path; an absent legacy file does not
create a legacy ownership directory. Busy unconditional ownership refuses with
`E_SETTINGS_UNCERTAIN:owner_busy`; it does not replay a write. Lock files remain
beside their corresponding files under `<filename>.settings-locks/`. Preserve
them while processes are active. Ordinary readers can observe a single atomically
published file. This is not a multi-file transaction, distributed lock, forced
thread termination, shutdown deadline, or guarantee against noncooperating writers.

## Preference migration and recovery

Legacy `preferred_<role>` settings migrate into `preferences.models`. Before
removing old keys, preferences retain `_meta.legacy_model_preferences_pending_v1`
with the selected settings path and exact source values. After verified settings
publication, preferences remove that pending record and set the existing
`legacy_model_preferences_v1` completion marker. A new process resumes pending
work only when the path, source values and destination models agree; drift refuses
without rewriting either file. A present non-object pending record, including
`null`, is invalid and cannot be treated as an absent journal. Normal saves refuse while migration is pending.
Resume with `load_user_preferences[_async]` after resolving any reported conflict.

Old completion markers with leftover source keys are reconciled only when the
destination model values match. Conflicting histories are not silently combined.
Retain both files when recovering a failed migration. The pending record is
operational recovery data, not tamper-resistant evidence. Older binaries must not
write these files while a pending migration exists.

The default project-root `user_settings.json` still migrates to the durable path
on first read when the latter is absent. The destination is verified before
retiring matching legacy contents. A failure between publication and retirement
can leave both files; the durable destination takes precedence on later reads.
No automatic history merge or deletion of a conflicting legacy file is claimed.

CLI settings observation can fail during early capability selection or startup.
Both failures return a nonzero status and retain error context without claiming
onboarding success; the phase determines the existing critical/fatal diagnostic.
