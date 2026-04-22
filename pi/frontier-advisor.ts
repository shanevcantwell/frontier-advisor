/**
 * frontier-advisor — PI extension
 *
 * Gives the local model a tool for consulting frontier AI APIs.
 * Core logic in adapter.ts (testable standalone).
 * Tool definition in tool.ts (harness-agnostic).
 *
 * Resolves API keys from pi's AuthStorage (oauth or env var).
 *
 * Usage: place in ~/.pi/agent/extensions/ or .pi/extensions/
 */

import type { AgentToolResult, ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import type { ApiKeyResolver } from "./adapter.js";
import { consult } from "./adapter.js";
import { CONSULT_TOOL_DEFINITION } from "./tool.js";

/** Build an ApiKeyResolver that reads from pi's AuthStorage. */
function buildAuthStorageResolver(ctx: ExtensionContext): ApiKeyResolver {
  return async (provider) => {
    try {
      const apiKey = await ctx.modelRegistry.getApiKeyForProvider(provider);
      if (!apiKey) return undefined;
      // Base URL override via env var (e.g. for local proxies)
      const envKey = provider === "anthropic" ? "ANTHROPIC_BASE_URL" : "OPENAI_BASE_URL";
      const envDefault = provider === "anthropic" ? "https://api.anthropic.com" : "https://api.openai.com";
      return {
        apiKey,
        baseUrl: process.env[envKey] ?? envDefault,
      };
    } catch {
      return undefined;
    }
  };
}

export default function frontierAdvisorExtension(pi: ExtensionAPI) {
  pi.registerTool({
    ...CONSULT_TOOL_DEFINITION,
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      // Build key resolver from pi's auth storage (oauth or env var)
      const resolver = buildAuthStorageResolver(ctx);

      try {
        const result = await consult({
          question: params.question,
          context: params.context ?? "",
          systemPrompt: params.system_prompt || undefined,
          signal: signal ?? undefined,
          apiKeyResolver: resolver,
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
