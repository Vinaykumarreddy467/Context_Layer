/**
 * Context-layer plugin for OpenCode / OpenWork.
 *
 * Two hooks, one engine:
 *   1. `session.idle`  — fires after every model response. Shells out to
 *      hooks/context-layer-checkpoint.js, which estimates transcript tokens
 *      and only saves a handoff when the threshold is crossed (proactive).
 *   2. `experimental.session.compacting` — fires right before OpenCode
 *      compacts. Shells out to the shared Python engine (save_before_compact.py)
 *      so nothing is lost at the limit (reactive safety net).
 *
 * Install: `python setup_mcp.py` in your project deploys this file to
 * `.opencode/plugins/context-layer.ts` with the paths below filled in.
 * No config registration needed.
 *
 * Env: CONTEXT_LAYER_DIR (defaults to the context_layer checkout),
 *      CONTEXT_LAYER_CHECKPOINT_JS (defaults to the deployed hook),
 *      CONTEXT_LAYER_PYTHON (defaults to the context_layer venv python).
 */

import type { Plugin } from "@opencode-ai/plugin"

const CONTEXT_LAYER_DIR =
  process.env.CONTEXT_LAYER_DIR ?? "__CONTEXT_LAYER_DIR__"
const CHECKPOINT_JS =
  process.env.CONTEXT_LAYER_CHECKPOINT_JS ?? "__CHECKPOINT_JS__"
const CONTEXT_LAYER_PYTHON =
  process.env.CONTEXT_LAYER_PYTHON ?? "__CONTEXT_LAYER_PYTHON__"

export const ContextLayerPlugin: Plugin = async ({ project, client, $, directory }) => {
  const projectDir = directory ?? project?.path ?? process.cwd()

  async function transcriptFor(sessionID: string): Promise<string> {
    try {
      const messages = await client.session.messages({ id: sessionID })
      return messages
        .map((m: any) => `${m.role}: ${typeof m.content === "string" ? m.content : JSON.stringify(m.content)}`)
        .join("\n")
    } catch (err) {
      await client.app.log({
        body: { service: "context-layer", level: "warn",
                 message: "could not read session messages", extra: { error: String(err) } },
      })
      return ""
    }
  }

  return {
    "session.idle": async (input: any) => {
      const sessionID = input?.sessionID ?? input?.session?.id ?? input?.id
      if (!sessionID) return
      const transcript = await transcriptFor(sessionID)
      if (!transcript.trim()) return
      try {
        const result = await $`node ${CHECKPOINT_JS}`
          .cwd(projectDir)
          .env({ ...process.env, CONTEXT_LAYER_TRANSCRIPT: transcript })
          .text()
        if (result.trim()) {
          await client.app.log({
            body: { service: "context-layer", level: "info",
                     message: "checkpoint result", extra: { result } },
          })
        }
      } catch (err) {
        // Never block the session on our failure.
        await client.app.log({
          body: { service: "context-layer", level: "error",
                   message: "checkpoint failed", extra: { error: String(err) } },
        })
      }
    },

    "experimental.session.compacting": async (input: any, output: any) => {
      const sessionID = input?.sessionID ?? input?.session?.id ?? input?.id
      const transcript = await transcriptFor(sessionID)
      try {
        const result = await $`${CONTEXT_LAYER_PYTHON} ${CONTEXT_LAYER_DIR}/adapters/opencode/save_before_compact.py --cwd ${projectDir}`
          .cwd(CONTEXT_LAYER_DIR)
          .env({ ...process.env, CONTEXT_LAYER_TRANSCRIPT: transcript, CONTEXT_LAYER_SESSION_ID: sessionID ?? "" })
          .text()
        output.context?.push(
          `\n## Context Layer\nA detailed handoff for this task was saved outside OpenCode's own memory (project: ${project?.name ?? projectDir}).\n`
        )
        await client.app.log({
          body: { service: "context-layer", level: "info",
                   message: "handoff saved before compaction", extra: { result } },
        })
      } catch (err) {
        await client.app.log({
          body: { service: "context-layer", level: "error",
                   message: "failed to save handoff before compaction",
                   extra: { error: String(err) } },
        })
      }
    },
  }
}