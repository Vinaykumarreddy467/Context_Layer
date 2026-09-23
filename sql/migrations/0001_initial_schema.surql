-- ============================================================
-- Migration 0001: Initial Context Layer Schema
-- ============================================================

USE NS dev DB context_layer;

-- Schema version tracking table
DEFINE TABLE IF NOT EXISTS schema_version SCHEMAFULL;
DEFINE FIELD IF NOT EXISTS version ON schema_version TYPE int;
DEFINE FIELD IF NOT EXISTS applied_at ON schema_version TYPE datetime DEFAULT time::now();
DEFINE FIELD IF NOT EXISTS description ON schema_version TYPE string;
DEFINE INDEX IF NOT EXISTS version_idx ON schema_version FIELDS version UNIQUE;

-- Handoff table: stores context checkpoints
DEFINE TABLE IF NOT EXISTS handoff SCHEMAFULL;

DEFINE FIELD IF NOT EXISTS timestamp    ON handoff TYPE datetime   DEFAULT time::now();
DEFINE FIELD IF NOT EXISTS task_slug    ON handoff TYPE string;
DEFINE FIELD IF NOT EXISTS git_branch   ON handoff TYPE string;
DEFINE FIELD IF NOT EXISTS status       ON handoff TYPE string      DEFAULT 'open';
DEFINE FIELD IF NOT EXISTS decisions    ON handoff TYPE array<object>;
DEFINE FIELD IF NOT EXISTS decisions.*.text      ON handoff TYPE string;
DEFINE FIELD IF NOT EXISTS decisions.*.rationale ON handoff TYPE string;
DEFINE FIELD IF NOT EXISTS next_steps   ON handoff TYPE array<string>;
DEFINE FIELD IF NOT EXISTS raw_content  ON handoff TYPE string;
DEFINE FIELD IF NOT EXISTS summary      ON handoff TYPE option<string>;
DEFINE FIELD IF NOT EXISTS platform_session_id ON handoff TYPE option<string>;
DEFINE FIELD IF NOT EXISTS token_count  ON handoff TYPE int         DEFAULT 0;
DEFINE FIELD IF NOT EXISTS compacted    ON handoff TYPE bool         DEFAULT false;
DEFINE FIELD IF NOT EXISTS files        ON handoff TYPE option<array<string>>;
DEFINE FIELD IF NOT EXISTS refs         ON handoff TYPE option<array<string>>;
DEFINE FIELD IF NOT EXISTS embedding    ON handoff TYPE option<array<float>>;

-- Fast filtering indexes
DEFINE INDEX IF NOT EXISTS task_slug_idx  ON handoff FIELDS task_slug;
DEFINE INDEX IF NOT EXISTS git_branch_idx ON handoff FIELDS git_branch;
DEFINE INDEX IF NOT EXISTS status_idx     ON handoff FIELDS status;

-- Full-text (BM25) search over the markdown content
DEFINE ANALYZER IF NOT EXISTS handoff_analyzer TOKENIZERS blank, class FILTERS lowercase, snowball(english);
DEFINE INDEX IF NOT EXISTS raw_content_search ON handoff FIELDS raw_content
    FULLTEXT ANALYZER handoff_analyzer BM25 HIGHLIGHTS;

-- Semantic (vector) search over the markdown content
-- Embeddings are 384-dim (BAAI/bge-small-en-v1.5 via fastembed), computed locally.
DEFINE INDEX IF NOT EXISTS embedding_idx ON handoff FIELDS embedding
    HNSW DIMENSION 384 DIST COSINE TYPE F32;

-- Edge table: chains handoffs together (this one continues from that one)
DEFINE TABLE IF NOT EXISTS continues_from TYPE RELATION FROM handoff TO handoff SCHEMALESS;

-- The migration runner records this version after the schema statements succeed.
