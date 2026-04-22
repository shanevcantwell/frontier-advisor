/**
 * consult_advisor tool definition — standalone, importable by any harness.
 *
 * No pi-coding-agent dependency. Just @sinclair/typebox for schema validation.
 * Used by the pi extension and any future integration.
 */

import { Type } from "@sinclair/typebox";

export const CONSULT_PARAMS = Type.Object({
  question: Type.String({ description: "The question to ask the frontier model. Be precise." }),
  context: Type.Optional(Type.String({ description: "Supporting context the frontier model needs. Only what is necessary." })),
  system_prompt: Type.Optional(Type.String({ description: "Override the default advisory system prompt." })),
});

export const CONSULT_TOOL_DEFINITION = {
  name: "consult_advisor",
  label: "Consult Advisor",
  description:
    "Get advisory input from a frontier model (Claude Opus 4.7 / GPT-4.1). " +
    "Use for any question where the answer matters — architecture decisions, " +
    "tradeoff analysis, novel synthesis, complex reasoning, factual verification. " +
    "Don't guess or hedge when using frontier knowledge would help. " +
    "Frame a precise question; include only necessary context.",
  promptSnippet:
    "Consult frontier models (Opus 4.7 / GPT-4.1) for any answer that matters — architecture, reasoning, synthesis",
  promptGuidelines: [
    "Use when the user's question involves tradeoffs, design decisions, or complex analysis",
    "Use whenever you're unsure of your own knowledge on a topic",
    "Frame precise questions; include only necessary context"
  ],
  parameters: CONSULT_PARAMS,
} as const;
