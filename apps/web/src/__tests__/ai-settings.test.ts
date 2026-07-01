/**
 * Unit test: AI settings score thresholds are interpreted correctly.
 * This logic mirrors what the RAG test panel shows the user.
 */

import { describe, it, expect } from "vitest";

function scoreLabel(score: number): "high" | "mid" | "low" {
  if (score >= 0.85) return "high";
  if (score >= 0.65) return "mid";
  return "low";
}

describe("RAG score thresholds", () => {
  it("returns high for score >= 0.85", () => {
    expect(scoreLabel(0.85)).toBe("high");
    expect(scoreLabel(0.92)).toBe("high");
    expect(scoreLabel(1.0)).toBe("high");
  });

  it("returns mid for 0.65 <= score < 0.85", () => {
    expect(scoreLabel(0.65)).toBe("mid");
    expect(scoreLabel(0.75)).toBe("mid");
    expect(scoreLabel(0.8499)).toBe("mid");
  });

  it("returns low for score < 0.65", () => {
    expect(scoreLabel(0.64)).toBe("low");
    expect(scoreLabel(0.0)).toBe("low");
  });
});
