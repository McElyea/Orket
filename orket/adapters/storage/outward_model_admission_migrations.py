from __future__ import annotations

from orket.adapters.storage.sqlite_migrations import SQLiteMigration

# Preserve the original schema for copied migration and old-writer refusal proof.
OUTWARD_MODEL_ADMISSION_MIGRATIONS = [SQLiteMigration(version=1, name="durable_outward_model_admission", statements=(
    """CREATE TABLE outward_model_admissions (
        run_id TEXT NOT NULL, execution_generation INTEGER NOT NULL CHECK (execution_generation >= 1),
        turn INTEGER NOT NULL CHECK (turn >= 1), step_index INTEGER NOT NULL CHECK (step_index >= 0),
        inputs_json TEXT NOT NULL, inputs_digest TEXT NOT NULL, state TEXT NOT NULL,
        created_at TEXT NOT NULL, owner_id TEXT, claimed_at TEXT, result_json TEXT, result_digest TEXT,
        observed_at TEXT, published_at TEXT,
        PRIMARY KEY (run_id, execution_generation, turn, step_index),
        CHECK (state IN ('ready', 'claimed', 'observed', 'published')),
        CHECK ((state = 'ready' AND owner_id IS NULL AND claimed_at IS NULL)
            OR (state != 'ready' AND owner_id IS NOT NULL AND length(owner_id) > 0 AND claimed_at IS NOT NULL)),
        CHECK ((state IN ('ready', 'claimed') AND result_json IS NULL AND result_digest IS NULL AND observed_at IS NULL)
            OR (state IN ('observed', 'published') AND result_json IS NOT NULL AND result_digest IS NOT NULL AND observed_at IS NOT NULL)),
        CHECK ((state = 'published') = (published_at IS NOT NULL))
    )""",
    """CREATE TRIGGER outward_model_admission_identity BEFORE UPDATE ON outward_model_admissions
    WHEN NEW.run_id IS NOT OLD.run_id OR NEW.execution_generation IS NOT OLD.execution_generation
      OR NEW.turn IS NOT OLD.turn OR NEW.step_index IS NOT OLD.step_index
      OR NEW.inputs_json IS NOT OLD.inputs_json OR NEW.inputs_digest IS NOT OLD.inputs_digest
      OR NEW.created_at IS NOT OLD.created_at
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_IMMUTABLE'); END""",
    """CREATE TRIGGER outward_model_admission_transition BEFORE UPDATE ON outward_model_admissions
    WHEN NOT ((OLD.state = 'ready' AND NEW.state = 'claimed')
      OR (OLD.state = 'claimed' AND NEW.state = 'observed')
      OR (OLD.state = 'observed' AND NEW.state = 'published'))
      OR (OLD.owner_id IS NOT NULL AND (NEW.owner_id IS NOT OLD.owner_id OR NEW.claimed_at IS NOT OLD.claimed_at))
      OR (OLD.result_json IS NOT NULL AND (NEW.result_json IS NOT OLD.result_json
        OR NEW.result_digest IS NOT OLD.result_digest OR NEW.observed_at IS NOT OLD.observed_at))
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_TRANSITION'); END""",
    """CREATE TRIGGER outward_model_admission_insert BEFORE INSERT ON outward_model_admissions
    WHEN NEW.state != 'ready' OR EXISTS (SELECT 1 FROM outward_model_admissions WHERE
      run_id = NEW.run_id AND execution_generation = NEW.execution_generation AND turn = NEW.turn AND step_index = NEW.step_index)
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_RETAINED'); END""",
    """CREATE TRIGGER outward_model_admission_delete BEFORE DELETE ON outward_model_admissions
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_RETAINED'); END""",
))]

OUTWARD_MODEL_ADMISSION_MIGRATIONS.append(SQLiteMigration(version=2, name="retained_fenced_model_attempts", statements=(
    """CREATE TABLE outward_model_attempts_v2 (
        run_id TEXT NOT NULL, execution_generation INTEGER NOT NULL CHECK (execution_generation >= 1),
        turn INTEGER NOT NULL CHECK (turn >= 1), step_index INTEGER NOT NULL CHECK (step_index >= 0),
        inputs_json TEXT NOT NULL, inputs_digest TEXT NOT NULL, state TEXT NOT NULL,
        created_at TEXT NOT NULL, owner_id TEXT, claimed_at TEXT, result_json TEXT, result_digest TEXT,
        observed_at TEXT, published_at TEXT,
        fencing_generation INTEGER NOT NULL DEFAULT 1 CHECK (fencing_generation >= 1),
        evidence_layout_version INTEGER NOT NULL DEFAULT 1 CHECK (evidence_layout_version IN (1, 2)),
        recovery_decision_id TEXT, recovery_records_digest TEXT,
        PRIMARY KEY (run_id, execution_generation, turn, step_index, fencing_generation),
        CHECK (state IN ('ready', 'claimed', 'observed', 'published')),
        CHECK ((state = 'ready' AND owner_id IS NULL AND claimed_at IS NULL)
            OR (state != 'ready' AND owner_id IS NOT NULL AND length(owner_id) > 0 AND claimed_at IS NOT NULL)),
        CHECK ((state IN ('ready', 'claimed') AND result_json IS NULL AND result_digest IS NULL AND observed_at IS NULL)
            OR (state IN ('observed', 'published') AND result_json IS NOT NULL AND result_digest IS NOT NULL AND observed_at IS NOT NULL)),
        CHECK ((state = 'published') = (published_at IS NOT NULL)),
        CHECK ((fencing_generation = 1 AND recovery_decision_id IS NULL AND recovery_records_digest IS NULL) OR
            (fencing_generation > 1 AND evidence_layout_version = 2 AND recovery_decision_id IS NOT NULL
             AND length(recovery_decision_id) > 0 AND recovery_records_digest IS NOT NULL AND length(recovery_records_digest) = 64))
    )""",
    """INSERT INTO outward_model_attempts_v2 (
        run_id, execution_generation, turn, step_index, inputs_json, inputs_digest, state,
        created_at, owner_id, claimed_at, result_json, result_digest, observed_at, published_at)
    SELECT run_id, execution_generation, turn, step_index, inputs_json, inputs_digest, state,
        created_at, owner_id, claimed_at, result_json, result_digest, observed_at, published_at FROM outward_model_admissions""",
    "DROP TABLE outward_model_admissions",
    """CREATE TRIGGER outward_model_attempt_identity BEFORE UPDATE ON outward_model_attempts_v2
    WHEN NEW.run_id IS NOT OLD.run_id OR NEW.execution_generation IS NOT OLD.execution_generation
      OR NEW.turn IS NOT OLD.turn OR NEW.step_index IS NOT OLD.step_index
      OR NEW.inputs_json IS NOT OLD.inputs_json OR NEW.inputs_digest IS NOT OLD.inputs_digest
      OR NEW.created_at IS NOT OLD.created_at OR NEW.fencing_generation IS NOT OLD.fencing_generation
      OR NEW.evidence_layout_version IS NOT OLD.evidence_layout_version OR NEW.recovery_decision_id IS NOT OLD.recovery_decision_id
      OR NEW.recovery_records_digest IS NOT OLD.recovery_records_digest
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_IMMUTABLE'); END""",
    """CREATE TRIGGER outward_model_attempt_transition BEFORE UPDATE ON outward_model_attempts_v2
    WHEN NOT ((OLD.state = 'ready' AND NEW.state = 'claimed')
      OR (OLD.state = 'claimed' AND NEW.state = 'observed')
      OR (OLD.state = 'observed' AND NEW.state = 'published'))
      OR OLD.fencing_generation != (SELECT MAX(fencing_generation) FROM outward_model_attempts_v2 WHERE
        run_id = OLD.run_id AND execution_generation = OLD.execution_generation AND turn = OLD.turn AND step_index = OLD.step_index)
      OR (OLD.owner_id IS NOT NULL AND (NEW.owner_id IS NOT OLD.owner_id OR NEW.claimed_at IS NOT OLD.claimed_at))
      OR (OLD.result_json IS NOT NULL AND (NEW.result_json IS NOT OLD.result_json
        OR NEW.result_digest IS NOT OLD.result_digest OR NEW.observed_at IS NOT OLD.observed_at))
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_TRANSITION'); END""",
    """CREATE TRIGGER outward_model_attempt_insert BEFORE INSERT ON outward_model_attempts_v2
    WHEN NEW.state != 'ready' OR NEW.evidence_layout_version != 2 OR
      NEW.fencing_generation != 1 + COALESCE((SELECT MAX(fencing_generation) FROM outward_model_attempts_v2 WHERE
        run_id = NEW.run_id AND execution_generation = NEW.execution_generation AND turn = NEW.turn AND step_index = NEW.step_index), 0)
      OR (NEW.fencing_generation > 1 AND NOT EXISTS (SELECT 1 FROM outward_model_attempts_v2 WHERE
        run_id = NEW.run_id AND execution_generation = NEW.execution_generation AND turn = NEW.turn AND step_index = NEW.step_index
        AND fencing_generation = NEW.fencing_generation - 1 AND state = 'claimed' AND result_json IS NULL
        AND inputs_json = NEW.inputs_json AND inputs_digest = NEW.inputs_digest))
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_RETAINED'); END""",
    """CREATE TRIGGER outward_model_attempt_delete BEFORE DELETE ON outward_model_attempts_v2
    BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_MODEL_ADMISSION_RETAINED'); END""",
)))
side_effecting = True
