/**
 * Integration test — live API calls against Anthropic/OpenAI.
 * Requires ANTHROPIC_API_KEY and/or OPENAI_API_KEY in environment.
 */

import { describe, it, expect } from "vitest";
import { consult } from "./adapter.js";

describe("live API", () => {
  it("calls Anthropic Opus with a question", async () => {
    const result = await consult({
      question: "What's the difference between optimistic and pessimistic locking? One sentence.",
    });
    
    expect(result).toBeDefined();
    console.log(`Provider: ${result.provider}`);
    console.log(`Model: ${result.model}`);
    console.log(`Response: "${result.response}"`);
  });

  it("includes metadata", async () => {
    const result = await consult({ question: "Hi" });
    
    expect(result.provider).toBeDefined();
    expect(result.model).toBeDefined();
    expect(typeof result.inputTokens).toBe("number");
    expect(typeof result.outputTokens).toBe("number");
    expect(typeof result.latencyMs).toBe("number");
  });

  it("fails with no credentials", async () => {
    const saved = { 
      ant: process.env.ANTHROPIC_API_KEY, 
      oai: process.env.OPENAI_API_KEY 
    };
    
    delete process.env.ANTHROPIC_API_KEY;
    delete process.env.OPENAI_API_KEY;

    await expect(consult({ question: "test" })).rejects.toThrow();
    
    Object.assign(process.env, saved);
  });
});
