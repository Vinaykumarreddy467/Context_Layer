/**
 * OpenCode adapter for the context layer.
 *
 * Uses OpenCode's official `experimental.session.compacting` plugin hook,
 * which fires before OpenCode generates its own compaction summary --
 * the OpenCode equivalent of Claude Code's PreCompact hook. (Confirmed
 * against OpenCode's own plugin docs at opencode.ai/docs/plugins; the
 * "experimental." prefix means this API name could still change in a
 * future OpenCode release -- check their changelog if this stops firing.)
 *
 * Install: drop this file in `.opencode/plugins/context-layer.ts` in
 * your project (or the equivalent global plugins directory).
 *
 * This shells out to the same Python engine used by every other adapter
 * (auto_handoff.py) rather than reimplementing anything in TypeScript --
 * one engine, many thin adapters.
 */

import type { Plugin } from "@opencode-ai/plugin"

// Point this at your context_layer project directory.
const CONTEXT_LAYER_DIR = process.env.CONTEXT_LAYER_DIR ?? "/path/to/context_layer"

export const ContextLayerPlugin: Plugin = async ({ project, client, $, directory }) => {
  return {
    "experimental.session.compacting": async (input, output) => {
      // task_slug resolution lives in Python (project_identity.py), so every
      // adapter agrees on the same identity -- pass the project directory
      // through and let save_before_compact.py resolve it.
      const projectDir = directory ?? project?.path ?? process.cwd()

      // NOTE: verify this call against the current OpenCode SDK -- the
      // method to fetch a session's messages may be named differently
      // (e.g. client.session.messages(...)). Check the SDK types in
      // node_modules/@opencode-ai/plugin if this errors.
      let transcriptText = ""
      try {
        const messages = await client.session.messages({ id: input.sessionID })
        transcriptText = messages
          .map((m: any) => `${m.role}: ${typeof m.content === "string" ? m.content : JSON.stringify(m.content)}`)
          .join("\n")
      } catch (err) {
        await client.app.log({
          body: { service: "context-layer", level: "warn",
                   message: "could not read session messages, using compaction input only",
                   extra: { error: String(err) } },
        })
      }

      try {
        // Shell out to the shared Python engine, same one every other
        // adapter uses -- keeps the summarization logic in one place.
        const result = await $`python ${CONTEXT_LAYER_DIR}/adapters/opencode/save_before_compact.py --cwd ${projectDir}`
          .cwd(CONTEXT_LAYER_DIR)
          .env({ ...process.env, CONTEXT_LAYER_TRANSCRIPT: transcriptText, CONTEXT_LAYER_SESSION_ID: input.sessionID })
          .text()

        // Also inject a short pointer into OpenCode's own compaction
        // summary, so its native continuation prompt mentions that a
        // fuller record exists in the context layer.
        output.context.push(
          `\n## Context Layer\nA detailed handoff for this task was also saved outside OpenCode's own memory (project: ${project.name}).\n`
        )

        await client.app.log({
          body: { service: "context-layer", level: "info",
                   message: "handoff saved before compaction", extra: { result } },
        })
      } catch (err) {
        // Never block OpenCode's own compaction on our failure.
        await client.app.log({
          body: { service: "context-layer", level: "error",
                   message: "failed to save handoff before compaction",
                   extra: { error: String(err) } },
        })
      }
    },
  }
}
