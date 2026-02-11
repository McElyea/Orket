-- 001_runtime_indexes.sql
-- Adds indexes used by runtime query paths. Idempotent.

CREATE TABLE IF NOT EXISTS _schema_migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_build_status ON issues(build_id, status);
CREATE INDEX IF NOT EXISTS idx_issues_session_id ON issues(session_id);
CREATE INDEX IF NOT EXISTS idx_comments_issue_id ON comments(issue_id);
CREATE INDEX IF NOT EXISTS idx_card_transactions_card_id ON card_transactions(card_id);
