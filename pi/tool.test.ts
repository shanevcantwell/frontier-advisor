/**
 * Tests for tool definition (tool.ts).
 *
 * Verifies the consult_advisor tool schema and metadata without
 * requiring pi-coding-agent or the full harness.
 */

import { describe, it, expect } from "vitest";
import { CONSULT_TOOL_DEFINITION, CONSULT_PARAMS } from "./tool.js";
import { Type } from "@sinclair/typebox";

describe("Tool definition", () => {
  it("has correct tool name", () => {
    expect(CONSULT_TOOL_DEFINITION.name).toBe("consult_advisor");
  });

  it("has human-readable label", () => {
    expect(CONSULT_TOOL_DEFINITION.label).toBe("Consult Advisor");
  });

  it("has descriptive LLM-facing description", () => {
    expect(CONSULT_TOOL_DEFINITION.description).toContain("frontier AI");
    expect(CONSULT_TOOL_DEFINITION.description).toContain("complex reasoning");
  });

  it("has promptSnippet for system prompt injection", () => {
    expect(CONSULT_TOOL_DEFINITION.promptSnippet).toBeDefined();
    expect(CONSULT_TOOL_DEFINITION.promptSnippet).toContain("frontier models");
  });

  it("has promptGuidelines", () => {
    expect(CONSULT_TOOL_DEFINITION.promptGuidelines).toBeDefined();
    expect(Array.isArray(CONSULT_TOOL_DEFINITION.promptGuidelines)).toBe(true);
    expect(CONSULT_TOOL_DEFINITION.promptGuidelines.length).toBe(3);
  });

  it("third guideline mentions peer treatment", () => {
    expect(CONSULT_TOOL_DEFINITION.promptGuidelines[2]).toContain("peer");
  });
});

describe("Parameter schema", () => {
  it("schema is a TypeBox object", () => {
    expect(CONSULT_PARAMS).toBeDefined();
    expect(CONSULT_PARAMS.type).toBe("object");
  });

  it("has question property", () => {
    expect(CONSULT_PARAMS.properties).toHaveProperty("question");
    expect(CONSULT_PARAMS.properties.question.type).toBe("string");
    expect(CONSULT_PARAMS.properties.question.description).toContain("frontier model");
  });

  it("has context property (optional)", () => {
    expect(CONSULT_PARAMS.properties).toHaveProperty("context");
    expect(CONSULT_PARAMS.properties.context.description).toContain("Supporting context");
  });

  it("has system_prompt property (optional)", () => {
    expect(CONSULT_PARAMS.properties).toHaveProperty("system_prompt");
    expect(CONSULT_PARAMS.properties.system_prompt.description).toContain("Override");
  });

  it("question is required", () => {
    expect(CONSULT_PARAMS.required).toContain("question");
  });

  it("context is not required", () => {
    expect(CONSULT_PARAMS.required).not.toContain("context");
  });

  it("system_prompt is not required", () => {
    expect(CONSULT_PARAMS.required).not.toContain("system_prompt");
  });
});
