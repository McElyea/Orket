from __future__ import annotations

from orket.adapters.storage.sqlite_migrations import SQLiteMigration

OUTWARD_APPROVAL_MIGRATIONS = [
    SQLiteMigration(version=1, name="create_outward_approvals", statements=(
        """CREATE TABLE IF NOT EXISTS outward_approval_proposals (
            proposal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, namespace TEXT NOT NULL,
            tool TEXT NOT NULL, args_preview_json TEXT NOT NULL, context_summary TEXT NOT NULL,
            risk_level TEXT NOT NULL, submitted_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            status TEXT NOT NULL, operator_ref TEXT, decision TEXT, reason TEXT, note TEXT, decided_at TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_outward_approvals_status_expires ON outward_approval_proposals (status, expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_outward_approvals_run ON outward_approval_proposals (run_id)",
    )),
    SQLiteMigration(version=2, name="immutable_outward_authorization", statements=(
        "ALTER TABLE outward_approval_proposals RENAME TO outward_approval_proposals_v2",
        "ALTER TABLE outward_approval_proposals_v2 ADD COLUMN authorization_json TEXT",
        "ALTER TABLE outward_approval_proposals_v2 ADD COLUMN authorization_digest TEXT",
        # Retiring the old table name makes old readers/writers fail closed.
        """CREATE TRIGGER outward_approval_no_replace BEFORE INSERT ON outward_approval_proposals_v2
            WHEN EXISTS (SELECT 1 FROM outward_approval_proposals_v2 WHERE proposal_id = NEW.proposal_id)
            BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_PROPOSAL_IMMUTABLE'); END""",
        """CREATE TRIGGER outward_approval_binding_immutable BEFORE UPDATE ON outward_approval_proposals_v2
            WHEN NEW.proposal_id IS NOT OLD.proposal_id OR NEW.run_id IS NOT OLD.run_id
              OR NEW.namespace IS NOT OLD.namespace OR NEW.tool IS NOT OLD.tool
              OR NEW.args_preview_json IS NOT OLD.args_preview_json
              OR NEW.context_summary IS NOT OLD.context_summary OR NEW.risk_level IS NOT OLD.risk_level
              OR NEW.submitted_at IS NOT OLD.submitted_at OR NEW.expires_at IS NOT OLD.expires_at
              OR NEW.authorization_json IS NOT OLD.authorization_json
              OR NEW.authorization_digest IS NOT OLD.authorization_digest
            BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_AUTHORIZATION_IMMUTABLE'); END""",
        """CREATE TRIGGER outward_approval_decision_immutable BEFORE UPDATE ON outward_approval_proposals_v2
            WHEN OLD.status != 'pending' AND (NEW.status IS NOT OLD.status
              OR NEW.operator_ref IS NOT OLD.operator_ref OR NEW.decision IS NOT OLD.decision
              OR NEW.reason IS NOT OLD.reason OR NEW.note IS NOT OLD.note OR NEW.decided_at IS NOT OLD.decided_at)
            BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_DECISION_IMMUTABLE'); END""",
        """CREATE TRIGGER outward_approval_no_delete BEFORE DELETE ON outward_approval_proposals_v2
            BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_HISTORY_RETAINED'); END""",
    )),
]
