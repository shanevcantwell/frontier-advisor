/**
 * frontier-advisor — PI extension
 *
 * Gives the local model a tool for consulting frontier AI APIs.
 * Core logic in adapter.ts (testable standalone).
 * Tool definition in tool.ts (harness-agnostic).
 *
 * Usage: place in ~/.pi/agent/extensions/ or .pi/extensions/
 */

import type { AgentToolResult, ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { consult } from "./adapter.js";
import { CONSULT_TOOL_DEFINITION } from "./tool.js";

export default function frontierAdvisorExtension(pi: ExtensionAPI) {
  pi.registerTool({
    ...CONSULT_TOOL_DEFINITION,
    async execute(_toolCallId, params, signal) {
      try {
        const result = await consult({
          question: params.question,
          context: params.context ?? "",
          systemPrompt: params.system_prompt || undefined,
          signal: signal ?? undefined,
        });

        return {
          content: [{ type: "text", text: JSON.stringify({
            status: "ok",
            advisory_response: result.response,
            metadata: {
              provider: result.provider,
              model: result.model,
              input_tokens: result.inputTokens,
              output_tokens: result.outputTokens,
              latency_ms: result.latencyMs,
            },
          }, null, 2) }],
          details: {
            provider: result.provider,
            model: result.model,
            inputTokens: result.inputTokens,
            outputTokens: result.outputTokens,
            latencyMs: result.latencyMs,
          },
        } as AgentToolResult;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        return {
          content: [{ type: "text", text: JSON.stringify({ status: "error", detail: msg }, null, 2) }],
          details: { error: msg },
        } as AgentToolResult;
      }
    },
  });
}
