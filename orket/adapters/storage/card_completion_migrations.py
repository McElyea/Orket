"""Final completion references and conservative backstops for direct SQL writes."""
from __future__ import annotations

from orket.adapters.storage.sqlite_migrations import SQLiteMigration

# These are the bound input columns of card schema v2, excluding support fields.
_INPUT_COLUMNS = (
    "id", "session_id", "build_id", "seat", "summary", "type", "priority", "sprint", "assignee",
    "retry_count", "max_retries", "params_json", "depends_on_json",
)
_INPUT_CHANGE = " OR ".join(f"NEW.{column} IS NOT OLD.{column}" for column in _INPUT_COLUMNS)

CARD_COMPLETION_MIGRATION = SQLiteMigration(
    version=2, name="card_completion_acceptance", statements=(
        "ALTER TABLE issues ADD COLUMN completion_generation INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE issues ADD COLUMN completion_context_json TEXT",
        "ALTER TABLE issues ADD COLUMN completion_ref TEXT",
        """CREATE TABLE card_completion_commits (
            completion_ref TEXT PRIMARY KEY, card_id TEXT NOT NULL, target_status TEXT NOT NULL,
            context_json TEXT NOT NULL, receipt_json TEXT NOT NULL
        )""",
        """CREATE TRIGGER card_completion_commits_no_update BEFORE UPDATE ON card_completion_commits
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_RECEIPT_IMMUTABLE'); END""",
        """CREATE TRIGGER card_completion_commits_no_delete BEFORE DELETE ON card_completion_commits
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_RECEIPT_IMMUTABLE'); END""",
        """CREATE TRIGGER card_completion_no_success_insert BEFORE INSERT ON issues
            WHEN lower(NEW.status) IN ('done', 'guard_approved')
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_INSERT_REQUIRES_REVIEW'); END""",
        """CREATE TRIGGER card_completion_require_receipt BEFORE UPDATE OF status, completion_ref, completion_context_json ON issues
            WHEN lower(NEW.status) IN ('done', 'guard_approved')
            AND (NEW.status IS NOT OLD.status OR NEW.completion_ref IS NOT OLD.completion_ref
                 OR NEW.completion_context_json IS NOT OLD.completion_context_json)
            AND NOT EXISTS (SELECT 1 FROM card_completion_commits c
                WHERE c.completion_ref = NEW.completion_ref AND c.card_id = NEW.id
                  AND c.target_status = NEW.status AND c.context_json = NEW.completion_context_json)
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_RECEIPT_REQUIRED'); END""",
        f"""CREATE TRIGGER card_completion_no_terminal_input_change BEFORE UPDATE ON issues
            WHEN lower(NEW.status) IN ('done', 'guard_approved') AND ({_INPUT_CHANGE})
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_REOPEN_REQUIRED'); END""",
        f"""CREATE TRIGGER card_completion_invalidate_changed_inputs AFTER UPDATE ON issues
            WHEN lower(NEW.status) NOT IN ('done', 'guard_approved')
            AND (NEW.status IS NOT OLD.status OR {_INPUT_CHANGE})
            AND NEW.completion_generation = OLD.completion_generation
            BEGIN UPDATE issues SET completion_generation = OLD.completion_generation + 1,
                completion_context_json = NULL, completion_ref = NULL WHERE id = NEW.id; END""",
        """CREATE TRIGGER card_completion_no_bound_card_delete BEFORE DELETE ON issues
            WHEN OLD.completion_generation > 0
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_ARCHIVE_REQUIRED'); END""",
        """CREATE TRIGGER card_completion_no_identity_change BEFORE UPDATE OF id ON issues
            WHEN NEW.id IS NOT OLD.id
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_IDENTITY_IMMUTABLE'); END""",
        """CREATE TRIGGER card_completion_no_terminal_generation_change BEFORE UPDATE OF completion_generation ON issues
            WHEN lower(NEW.status) IN ('done', 'guard_approved')
              AND NEW.completion_generation IS NOT OLD.completion_generation
            BEGIN SELECT RAISE(ABORT, 'E_CARD_COMPLETION_REOPEN_REQUIRED'); END""",
    ),
)
side_effecting = True
