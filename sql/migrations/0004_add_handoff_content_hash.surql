-- ============================================================
-- Migration 0004: content_hash for duplicate-checkpoint detection
-- ============================================================

-- SHA-256 over whitespace-normalized raw_content, computed in Python
-- (core._content_hash). The duplicate guard matches task_slug plus
-- content_hash within a 60s window. platform_session_id alone is no
-- longer treated as a duplicate signal.
-- Historic records have no hash (option<string>). They still load and
-- resume normally and are simply never matched by the guard.
DEFINE FIELD IF NOT EXISTS content_hash ON handoff TYPE option<string>;

-- Suitable for the guard query: WHERE task_slug = $slug AND content_hash = $hash
DEFINE INDEX IF NOT EXISTS task_content_hash_idx ON handoff FIELDS task_slug, content_hash;