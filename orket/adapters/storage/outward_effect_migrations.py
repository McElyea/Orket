from __future__ import annotations

from orket.adapters.storage.sqlite_migrations import SQLiteMigration

OUTWARD_EFFECT_MIGRATIONS = [
    SQLiteMigration(version=1, name="outward_effect_ownership", statements=(
        """CREATE TABLE IF NOT EXISTS outward_effects (
        effect_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE, binding_digest TEXT NOT NULL,
        owner_id TEXT NOT NULL, fencing_generation INTEGER NOT NULL CHECK (fencing_generation >= 1),
        state TEXT NOT NULL, claimed_at TEXT NOT NULL, journal_entry_id TEXT NOT NULL,
        dispatched_at TEXT, receipt_json TEXT, receipt_digest TEXT, published_at TEXT
    )""",
        """CREATE TRIGGER IF NOT EXISTS outward_effect_identity_immutable
        BEFORE UPDATE ON outward_effects WHEN NEW.effect_id IS NOT OLD.effect_id
          OR NEW.proposal_id IS NOT OLD.proposal_id OR NEW.binding_digest IS NOT OLD.binding_digest
          OR NEW.owner_id IS NOT OLD.owner_id OR NEW.fencing_generation IS NOT OLD.fencing_generation
          OR NEW.claimed_at IS NOT OLD.claimed_at
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_EFFECT_IDENTITY_IMMUTABLE'); END""",
        """CREATE TRIGGER IF NOT EXISTS outward_effect_transition_guard
        BEFORE UPDATE ON outward_effects WHEN NOT (
          (OLD.state = 'claimed' AND NEW.state = 'dispatching') OR
          (OLD.state = 'dispatching' AND NEW.state = 'observed') OR
          (OLD.state = 'observed' AND NEW.state = 'published'))
          OR (OLD.dispatched_at IS NOT NULL AND NEW.dispatched_at IS NOT OLD.dispatched_at)
          OR (OLD.receipt_json IS NOT NULL AND (NEW.receipt_json IS NOT OLD.receipt_json
            OR NEW.receipt_digest IS NOT OLD.receipt_digest))
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_EFFECT_TRANSITION'); END""",
        """CREATE TRIGGER IF NOT EXISTS outward_effect_no_replace BEFORE INSERT ON outward_effects
        WHEN EXISTS (SELECT 1 FROM outward_effects WHERE proposal_id = NEW.proposal_id OR effect_id = NEW.effect_id)
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_EFFECT_RETAINED'); END""",
        """CREATE TRIGGER IF NOT EXISTS outward_effect_no_delete BEFORE DELETE ON outward_effects
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_EFFECT_RETAINED'); END""",
    )),
    SQLiteMigration(version=2, name="outward_pre_intent_recovery", statements=(
        "ALTER TABLE outward_effects ADD COLUMN recovery_decision_id TEXT",
        "DROP TRIGGER outward_effect_identity_immutable",
        "DROP TRIGGER outward_effect_transition_guard",
        """CREATE TRIGGER outward_effect_identity_immutable BEFORE UPDATE ON outward_effects
            WHEN NEW.effect_id IS NOT OLD.effect_id OR NEW.proposal_id IS NOT OLD.proposal_id
              OR NEW.binding_digest IS NOT OLD.binding_digest OR NEW.claimed_at IS NOT OLD.claimed_at
            BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_EFFECT_IDENTITY_IMMUTABLE'); END""",
        """CREATE TRIGGER outward_effect_transition_guard BEFORE UPDATE ON outward_effects WHEN NOT (
            (OLD.state = 'claimed' AND NEW.state = 'claimed' AND OLD.dispatched_at IS NULL
              AND NEW.dispatched_at IS NULL AND NEW.owner_id != OLD.owner_id AND length(NEW.owner_id) > 0
              AND NEW.fencing_generation = OLD.fencing_generation + 1 AND NEW.journal_entry_id != OLD.journal_entry_id
              AND NEW.recovery_decision_id IS NOT NULL AND NEW.recovery_decision_id IS NOT OLD.recovery_decision_id
              AND length(NEW.recovery_decision_id) > 0)
            OR (NEW.owner_id = OLD.owner_id AND NEW.fencing_generation = OLD.fencing_generation
              AND NEW.recovery_decision_id IS OLD.recovery_decision_id AND (
              (OLD.state = 'claimed' AND NEW.state = 'dispatching') OR
              (OLD.state = 'dispatching' AND NEW.state = 'observed') OR
              (OLD.state = 'observed' AND NEW.state = 'published'))))
              OR (OLD.dispatched_at IS NOT NULL AND NEW.dispatched_at IS NOT OLD.dispatched_at)
              OR (OLD.receipt_json IS NOT NULL AND (NEW.receipt_json IS NOT OLD.receipt_json
                OR NEW.receipt_digest IS NOT OLD.receipt_digest))
            BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_EFFECT_TRANSITION'); END""",
    )),
]
