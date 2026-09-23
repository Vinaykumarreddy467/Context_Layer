-- ============================================================
-- CONTEXT LAYER: Complete SurrealQL Reference
-- Run sections top to bottom in Surrealist's query editor.
-- Assumes SurrealDB 3.0+ syntax (FULLTEXT ANALYZER).
-- If your instance is pre-3.0, swap FULLTEXT -> SEARCH.
-- ============================================================


-- ============================================================
-- 1. SETUP: namespace, database, schema
-- ============================================================

USE NS dev DB context_layer;

DEFINE TABLE handoff SCHEMAFULL;

DEFINE FIELD timestamp    ON handoff TYPE datetime   DEFAULT time::now();
DEFINE FIELD task_slug    ON handoff TYPE string;
DEFINE FIELD git_branch   ON handoff TYPE string;
DEFINE FIELD status       ON handoff TYPE string      DEFAULT 'open'; -- open | resumed | closed
DEFINE FIELD decisions    ON handoff TYPE array<object>;
DEFINE FIELD decisions.*.text      ON handoff TYPE string;
DEFINE FIELD decisions.*.rationale ON handoff TYPE string;
DEFINE FIELD next_steps   ON handoff TYPE array<string>;
DEFINE FIELD raw_content  ON handoff TYPE string;
DEFINE FIELD summary      ON handoff TYPE option<string>; -- optional: pre-existing records may lack it
DEFINE FIELD platform_session_id ON handoff TYPE option<string>; -- native session id of the originating platform; metadata only, never a linking key
DEFINE FIELD token_count  ON handoff TYPE int         DEFAULT 0;   -- for budget-aware compaction later
DEFINE FIELD compacted    ON handoff TYPE bool         DEFAULT false; -- true if this is a summarized/compacted record
DEFINE FIELD files        ON handoff TYPE option<array<string>>; -- file paths referenced (extracted at write time)
DEFINE FIELD refs         ON handoff TYPE option<array<string>>; -- issue/requirement refs: #123, ABC-123, GH-123, URLs

-- Fast filtering on the fields you'll query most
DEFINE INDEX task_slug_idx  ON handoff FIELDS task_slug;
DEFINE INDEX git_branch_idx ON handoff FIELDS git_branch;
DEFINE INDEX status_idx     ON handoff FIELDS status;

-- Full-text (BM25) search over the markdown content
DEFINE ANALYZER handoff_analyzer TOKENIZERS blank, class FILTERS lowercase, snowball(english);
DEFINE INDEX raw_content_search ON handoff FIELDS raw_content
    FULLTEXT ANALYZER handoff_analyzer BM25 HIGHLIGHTS;

-- Semantic (vector) search over the markdown content
-- Embeddings are 384-dim (BAAI/bge-small-en-v1.5 via fastembed), computed locally.
-- Optional: records without an embedding are simply skipped by the HNSW index.
DEFINE FIELD embedding ON handoff TYPE option<array<float>>;
DEFINE INDEX embedding_idx ON handoff FIELDS embedding
    HNSW DIMENSION 384 DIST COSINE TYPE F32;

-- Edge table: chains handoffs together (this one continues from that one)
DEFINE TABLE continues_from TYPE RELATION FROM handoff TO handoff SCHEMALESS;


-- ============================================================
-- 2. WRITE: creating and updating handoffs
-- ============================================================

-- 2.1 Create a fresh handoff (no predecessor)
CREATE handoff SET
    task_slug   = "implementing-auth",
    git_branch  = "feature/auth",
    status      = "open",
    decisions   = [{ text: "Use JWT over sessions", rationale: "Stateless, works across our two services" }],
    next_steps  = ["Add refresh token rotation", "Write integration tests"],
    raw_content = "## Auth implementation\n\nDecided on JWT because...",
    token_count = 480;

-- 2.2 Create a new handoff AND link it to its predecessor, atomically
BEGIN TRANSACTION;
LET $new = CREATE handoff SET
    task_slug   = "implementing-auth",
    git_branch  = "feature/auth",
    status      = "open",
    decisions   = [{ text: "Added refresh rotation", rationale: "Closes token-theft window" }],
    next_steps  = ["Deploy to staging"],
    raw_content = "## Continued from previous session\n\n...",
    token_count = 210;
RELATE $new->continues_from->handoff:abc456; -- replace with the actual predecessor id
COMMIT TRANSACTION;

-- 2.3 Mark a handoff as resumed (call this when a new session picks it up)
UPDATE handoff:abc456 SET status = "resumed";

-- 2.4 Append a next step to an existing handoff without overwriting the array
UPDATE handoff:abc456 SET next_steps += "Add rate limiting to login endpoint";

-- 2.5 Close out a handoff once its task is fully done
UPDATE handoff:abc456 SET status = "closed";


-- ============================================================
-- 3. READ: fetching handoffs
-- ============================================================

-- 3.1 Most recent handoff for a given task (what you load on RESUME)
SELECT * FROM handoff
    WHERE task_slug = "implementing-auth"
    ORDER BY timestamp DESC
    LIMIT 1;

-- 3.2 Most recent handoff on a given git branch
SELECT * FROM handoff
    WHERE git_branch = "feature/auth"
    ORDER BY timestamp DESC
    LIMIT 1;

-- 3.3 All open (unfinished) handoffs, newest first
SELECT * FROM handoff
    WHERE status != "closed"
    ORDER BY timestamp DESC;

-- 3.4 Single handoff by id
SELECT * FROM handoff:abc456;


-- ============================================================
-- 4. SEARCH: full-text and filtered search
-- ============================================================

-- 4.1 Plain full-text search across all handoffs
SELECT task_slug, raw_content, search::score(1) AS relevance
    FROM handoff
    WHERE raw_content @1@ "jwt authentication"
    ORDER BY relevance DESC;

-- 4.2 Full-text search scoped to one task (filter + search combined)
SELECT task_slug, raw_content, search::score(1) AS relevance
    FROM handoff
    WHERE task_slug = "implementing-auth"
      AND raw_content @1@ "refresh token"
    ORDER BY relevance DESC;

-- 4.3 Search with highlighted snippet returned
SELECT task_slug, search::highlight("<b>", "</b>", 1) AS snippet
    FROM handoff
    WHERE raw_content @1@ "rate limiting";


-- ============================================================
-- 5. GRAPH: walking the handoff chain
-- ============================================================

-- 5.1 Walk backward: everything this handoff continues from (oldest lineage)
SELECT ->continues_from->handoff.* FROM handoff:xyz123;

-- 5.2 Walk forward: what handoffs continued from this one
SELECT <-continues_from<-handoff.* FROM handoff:abc456;

-- 5.3 Full lineage in order (multi-hop traversal), newest to oldest
SELECT * FROM handoff:xyz123->continues_from->handoff->continues_from->handoff;


-- ============================================================
-- 6. MAINTENANCE: staleness, archiving, analytics
-- ============================================================

-- 6.1 Staleness check: flag handoffs older than 24h as stale
SELECT *,
    (time::now() - timestamp) > 24h AS is_stale
    FROM handoff
    WHERE task_slug = "implementing-auth"
    ORDER BY timestamp DESC
    LIMIT 1;

-- 6.2 Archive (delete) closed handoffs older than 90 days
DELETE handoff WHERE status = "closed" AND timestamp < time::now() - 90d;

-- 6.3 Count handoffs per task (see which tasks have the longest history)
SELECT task_slug, count() AS handoff_count
    FROM handoff
    GROUP BY task_slug
    ORDER BY handoff_count DESC;

-- 6.4 Total tokens currently stored per task (useful once you add compaction)
SELECT task_slug, math::sum(token_count) AS total_tokens
    FROM handoff
    GROUP BY task_slug;


-- ============================================================
-- 7. REALTIME (optional): live-subscribe to new handoffs
-- Useful if you build a dashboard or want an agent to react
-- the instant a new handoff is written.
-- ============================================================

LIVE SELECT * FROM handoff WHERE task_slug = "implementing-auth";
