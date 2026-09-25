#!/usr/bin/env node
// context-layer-checkpoint — proactive checkpoint trigger for OpenCode /
// OpenWork (session.idle) and Copilot (userPromptSubmitted).
//
// On every call: estimate transcript tokens, compare against the latest
// handoff for this task, and only when the threshold is crossed (and the
// last handoff is stale enough) shell out to the existing summarize path.
// Fast (<100ms) and silent when nothing needs saving. Never throws.
//
// Usage:
//   node context-layer-checkpoint.js [--transcript-file <path>]
//     transcript via CONTEXT_LAYER_TRANSCRIPT env, --transcript-file, or stdin
//     (raw text or a hook JSON payload with transcript_path / transcript)
//
// Config via env (defaults match the local dev setup):
//   CONTEXT_LAYER_CHECKPOINT_TOKENS   trigger when estimated tokens exceed this (default 50000)
//   CONTEXT_LAYER_MIN_INTERVAL        seconds since last handoff before re-triggering (default 600)
//   CONTEXT_LAYER_GROWTH_PCT          min growth vs last handoff's token_count to re-trigger (default 0.3)
//   CONTEXT_LAYER_URL / NS / DB / USER / PASS / PYTHON / CLI_DIR  (same as context-layer-handoff.js)
//   CONTEXT_LAYER_URL   http://127.0.0.1:8010  (requires SurrealDB started with --http)
//
// IMPORTANT: SurrealDB must be started with HTTP endpoint enabled:
//   surreal start --http --user root --pass root --bind 127.0.0.1:8010 rocksdb://./data/handoffs.db

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

function loadEnv() {
  const envPath = path.join(process.cwd(), ".env");
  if (fs.existsSync(envPath)) {
    const content = fs.readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith("#")) {
        const eqIdx = trimmed.indexOf("=");
        if (eqIdx > 0) {
          const key = trimmed.slice(0, eqIdx).trim();
          const val = trimmed.slice(eqIdx + 1).trim();
          if (!process.env[key]) {
            process.env[key] = val;
          }
        }
      }
    }
  }
}

loadEnv();

const SURREAL_HTTP_URL = process.env.CONTEXT_LAYER_URL || process.env.SURREAL_HTTP_URL || "http://127.0.0.1:8010";
const NS = process.env.CONTEXT_LAYER_NS || process.env.SURREAL_NS || "dev";
const DB = process.env.CONTEXT_LAYER_DB || process.env.SURREAL_DB || "context_layer";
const USER = process.env.CONTEXT_LAYER_USER || process.env.SURREAL_USER || "root";
const PASS = process.env.CONTEXT_LAYER_PASS || process.env.SURREAL_PASS || "root";
const PYTHON =
  process.env.CONTEXT_LAYER_PYTHON ||
  "C:\\Users\\Vinaykumar.R\\Downloads\\context_layer\\context_layer\\venv\\Scripts\\python.exe";
const CLI_DIR =
  process.env.CONTEXT_LAYER_CLI_DIR ||
  "C:\\Users\\Vinaykumar.R\\Downloads\\context_layer\\context_layer";
const TOKENS = Number(process.env.CONTEXT_LAYER_CHECKPOINT_TOKENS || 50000);
const MIN_INTERVAL = Number(process.env.CONTEXT_LAYER_MIN_INTERVAL || 600);
const GROWTH_PCT = Number(process.env.CONTEXT_LAYER_GROWTH_PCT || 0.3);

function fail(msg) {
  process.stderr.write(`[context-layer] ${msg}\n`);
  process.exit(0); // hooks must never fail the client
}

function autoSlug() {
  // Route through the shared package resolver so this
  // hook agrees with every other adapter: env var -> .context-layer.json.
  // If resolver fails (no identity file), exit cleanly - no identity = no handoff.
  try {
    const slug = execFileSync(
      PYTHON,
      ["-m", "context_layer.project_identity", "resolve", process.cwd()],
      { encoding: "utf-8", cwd: CLI_DIR }
    ).trim();
    if (slug) return slug;
  } catch (e) {
    // Resolver unavailable or no identity file - exit silently
    process.exit(0);
  }
  // Fallback: git branch (only if resolver unavailable)
  try {
    const branch = execFileSync("git", ["branch", "--show-current"], {
      encoding: "utf-8",
    })
      .trim();
    if (branch) return branch;
  } catch {
    /* not a git repo */
  }
  return require("path").basename(process.cwd());
}

function gitBranch() {
  try {
    return execFileSync("git", ["rev-parse", "--abbrev-ref", "HEAD"], {
      encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"],
    }).trim() || "unknown";
  } catch {
    return "unknown";
  }
}

async function latestHandoff(taskSlug) {
  const query = "SELECT id, timestamp, token_count FROM handoff WHERE task_slug = $slug ORDER BY timestamp DESC LIMIT 1;";
  const sqlUrl = new URL(`${SURREAL_HTTP_URL}/sql`);
  sqlUrl.searchParams.set("slug", taskSlug);
  let res;
  try {
    res = await fetch(sqlUrl, {
      method: "POST",
      headers: {
        Authorization: "Basic " + Buffer.from(`${USER}:${PASS}`).toString("base64"),
        "Content-Type": "text/plain",
        NS: NS,
        DB: DB,
        "surreal-ns": NS,
        "surreal-db": DB,
      },
      body: query,
    });
  } catch (e) {
    fail(`SurrealDB unreachable at ${SURREAL_HTTP_URL}: ${e.message}`);
  }
  if (!res.ok) fail(`SurrealDB HTTP ${res.status}`);
  const rows = await res.json();
  return rows?.[0]?.result?.[0] || null;
}

function shouldTrigger(tokens, prev) {
  if (tokens <= TOKENS) return false;
  if (!prev) return true; // crossed threshold, no handoff yet
  const prevTokens = Number(prev.token_count || 0);
  const grew = prevTokens === 0 || tokens - prevTokens > prevTokens * GROWTH_PCT;
  const ts = new Date(prev.timestamp).getTime();
  const stale = isNaN(ts) || (Date.now() - ts) / 1000 > MIN_INTERVAL;
  return grew && stale;
}

async function main() {
  const args = process.argv.slice(2);
  const tf = args.indexOf("--transcript-file");

  // Transcript sources, in order: --transcript-file, CONTEXT_LAYER_TRANSCRIPT
  // env (the OpenCode plugin's channel), then stdin — raw text, or a hook
  // JSON payload with a transcript_path / transcript field (Claude Code,
  // Copilot). Unrecognized JSON with no transcript = silent skip.
  let transcript = "";
  if (tf !== -1) {
    transcript = fs.readFileSync(args[tf + 1], "utf-8");
  } else if ((process.env.CONTEXT_LAYER_TRANSCRIPT || "").trim()) {
    transcript = process.env.CONTEXT_LAYER_TRANSCRIPT;
  } else {
    let stdin = fs.readFileSync(0, "utf-8");
    if (process.env.CONTEXT_LAYER_CHECKPOINT_DEBUG) {
      try { fs.writeFileSync(process.env.CONTEXT_LAYER_CHECKPOINT_DEBUG, stdin); } catch {}
    }
    if (stdin.trim().startsWith("{")) {
      try {
        const payload = JSON.parse(stdin);
        const tp = payload.transcript_path || payload.transcriptPath || payload.transcript;
        if (typeof tp === "string" && tp && fs.existsSync(tp)) {
          transcript = fs.readFileSync(tp, "utf-8");
        } else if (typeof tp === "string") {
          transcript = tp; // inline transcript text
        }
      } catch {
        transcript = "";
      }
    } else {
      transcript = stdin;
    }
  }

  if (!transcript.trim()) {
    process.exit(0); // nothing to checkpoint
  }

  const tokens = Math.ceil(transcript.length / 4);
  const taskSlug = autoSlug();
  const prev = await latestHandoff(taskSlug);

  if (!shouldTrigger(tokens, prev)) {
    process.exit(0); // silent fast path
  }

  const branch = gitBranch();
  const out = execFileSync(
    PYTHON,
    [CLI_DIR + "\\scripts\\handoff_cli.py", "summarize", taskSlug, branch],
    { encoding: "utf-8", input: transcript, env: { ...process.env, PYTHONIOENCODING: "utf-8" } }
  );
  let id = "";
  try {
    id = JSON.parse(out).id || "";
  } catch {
    /* non-JSON output */
  }
  process.stdout.write(
    `[context-layer] checkpoint fired: ~${tokens} tokens > ${TOKENS}, saved handoff ${id} (task=${taskSlug})\n`
  );
}

main().catch((e) => fail(e.message));
