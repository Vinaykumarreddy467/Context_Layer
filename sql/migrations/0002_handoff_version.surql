-- ============================================================
-- Migration 0002: Handoff schema version field
-- ============================================================

USE NS dev DB context_layer;

-- Version the handoff record schema so capsules/imports can detect
-- format drift (see export_capsule.py capsule_version line).
DEFINE FIELD IF NOT EXISTS version ON handoff TYPE int DEFAULT 1;