-- 002_webhook_indexes.sql
-- Adds webhook query indexes. Idempotent.

CREATE TABLE IF NOT EXISTS _schema_migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pr_review_cycles_status ON pr_review_cycles(status);
CREATE INDEX IF NOT EXISTS idx_review_failures_cycle ON review_failures(pr_key, cycle_number);
CREATE INDEX IF NOT EXISTS idx_webhook_events_type_created ON webhook_events(event_type, created_at);
