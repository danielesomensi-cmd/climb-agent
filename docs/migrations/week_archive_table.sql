-- A221: cold store for past week_plans (lazy-archive).
-- Run once in the Supabase SQL Editor BEFORE deploying the A221 backend.
--
-- Past weeks (week_start < N-1) are moved out of the hot users.state JSONB blob
-- into this table, read on demand only (never loaded by read_state). One row per
-- archived week. user_id is TEXT (mirrors session_logs/outdoor_logs) so the
-- '__legacy__' bucket and Clerk-mapped UUIDs both fit; no strict FK for the same
-- reason. RLS enabled, no policies (anon key blocked, service role bypasses) —
-- identical posture to the other 6 tables (RLS audit 2026-04-03).

CREATE TABLE IF NOT EXISTS week_archive (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  week_start TEXT NOT NULL,         -- Monday "YYYY-MM-DD", same key scheme as week_plans
  plan JSONB NOT NULL,              -- the unmodified, fully-resolved week plan
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, week_start)       -- upsert target; one archived copy per week
);

CREATE INDEX IF NOT EXISTS idx_week_archive_user_id ON week_archive(user_id);
CREATE INDEX IF NOT EXISTS idx_week_archive_user_week ON week_archive(user_id, week_start);

ALTER TABLE week_archive ENABLE ROW LEVEL SECURITY;
