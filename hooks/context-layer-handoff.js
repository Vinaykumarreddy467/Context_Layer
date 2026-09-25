#!/usr/bin/env node
// context-layer-handoff — shared SessionStart/context hook for Claude Code,
// Codex, VS Code Copilot, Cursor and Qoder.
//
//   --resume <task_slug>            Emit the latest handoff as markdown context
//                                   (wire into SessionStart / sessionStart hooks)
//   --resume-auto                   Same, but derive task_slug from the current
//                                   git branch (or directory name) -- keeps hook
//                                   configs static across projects
//   --summarize <task_slug> <branch> [--transcript-file <path>]
//                                   Auto-summarize a transcript into a handoff
//                                   via the context-layer venv (no API key needed)
//
// Config via env (defaults match the local dev setup):
//   CONTEXT_LAYER_URL   http://127.0.0.1:8010  (requires SurrealDB started with --http)
//   CONTEXT_LAYER_NS    dev
//   CONTEXT_LAYER_DB    context_layer
//   CONTEXT_LAYER_USER  root
//   CONTEXT_LAYER_PASS  root
//   CONTEXT_LAYER_PYTHON  path to the context_layer venv python.exe
//   CONTEXT_LAYER_CLI_DIR  path to the context_layer checkout
//
// IMPORTANT: SurrealDB must be started with HTTP endpoint enabled:
//   surreal start --http --user root --pass root --bind 127.0.0.1:8010 rocksdb://./data/handoffs.db
//
// Exit 0 on success (or nothing to resume), 1 on failure. Never throws.

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

function fail(msg) {
  process.stderr.write(`[context-layer] ${msg}\n`);
  process.exit(1);
}

async function resume(taskSlug) {
  const query = "SELECT * FROM handoff WHERE task_slug = $slug ORDER BY timestamp DESC LIMIT 1;";
  const sqlUrl = new URL(`${SURREAL_HTTP_URL}/sql`);
  sqlUrl.searchParams.set("slug", taskSlug);
  let res;
  try {
    res = await fetch(sqlUrl, {
      method: "POST",
headers: {
      Authorization: "Basic " + Buffer.from(`${USER}:${PASS}`).toString("base64"),
      "Content-Type": "text/plain",
      // SurrealDB 3.x renamed NS/DB to surreal-ns/surreal-db; send both for compat
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
  const handoff = rows?.[0]?.result?.[0];
  if (!handoff) {
    process.exit(0); // nothing to resume — not an error
  }
  const decisions = (handoff.decisions || [])
    .map((d) => `- **${d.text}** — ${d.rationale || ""}`)
    .join("\n");
  const steps = (handoff.next_steps || []).map((s) => `- ${s}`).join("\n");
  const out = [
    `# Context: ${handoff.task_slug}`,
    "",
    "Resuming from a previous session. Do not ask the user to re-explain this.",
    "",
    `## Summary`,
    handoff.summary || handoff.raw_content || "",
    "",
    decisions ? `## Decisions already made (do not relitigate)\n${decisions}` : "",
    steps ? `## Next steps\n${steps}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  process.stdout.write(out + "\n");
}

function summarize(taskSlug, branch, transcriptFile) {
  const cli = `${CLI_DIR}\\handoff_cli.py`;
  const args = [cli, "summarize", taskSlug, branch];
  if (transcriptFile) args.push("--transcript-file", transcriptFile);
  try {
    const out = execFileSync(PYTHON, args, {
      encoding: "utf-8",
      input: transcriptFile ? undefined : fs.readFileSync(0, "utf-8"),
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });
    process.stdout.write(out);
  } catch (e) {
    fail(`summarize failed: ${e.stderr || e.message}`);
  }
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

async function main() {
  const args = process.argv.slice(2);
  const cmd = args[0];
  if (cmd === "--resume") {
    if (!args[1]) fail("--resume needs a task_slug");
    await resume(args[1]);
  } else if (cmd === "--resume-auto") {
    await resume(autoSlug());
  } else if (cmd === "--summarize") {
    if (!args[1] || !args[2]) fail("--summarize needs task_slug and git_branch");
    const tf = args.indexOf("--transcript-file");
    summarize(args[1], args[2], tf !== -1 ? args[tf + 1] : undefined);
  } else {
    fail(`unknown command '${cmd}' (use --resume or --summarize)`);
  }
}

main().catch((e) => fail(e.message));
