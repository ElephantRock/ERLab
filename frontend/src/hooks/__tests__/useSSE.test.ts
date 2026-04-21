import { describe, it, expect } from "vitest";
import { isStageProgress, isDone } from "@/hooks/useSSE";

describe("isStageProgress", () => {
  it("returns true for valid stage progress object", () => {
    expect(isStageProgress({ stage: "gap_analysis", index: 2, total: 8, elapsed: 5.2 })).toBe(true);
  });

  it("returns false for heartbeat event", () => {
    expect(isStageProgress({ heartbeat: true })).toBe(false);
  });

  it("returns false for done event", () => {
    expect(isStageProgress({ done: true })).toBe(false);
  });

  it("returns false for null", () => {
    expect(isStageProgress(null)).toBe(false);
  });

  it("returns false for object missing stage field", () => {
    expect(isStageProgress({ index: 0, total: 8, elapsed: 0 })).toBe(false);
  });

  it("returns false for non-string stage", () => {
    expect(isStageProgress({ stage: 42, index: 0, total: 8, elapsed: 0 })).toBe(false);
  });
});

describe("isDone", () => {
  it("returns true for { done: true }", () => {
    expect(isDone({ done: true })).toBe(true);
  });

  it("returns false for stage progress object", () => {
    expect(isDone({ stage: "export", index: 7, total: 8, elapsed: 30 })).toBe(false);
  });

  it("returns false for null", () => {
    expect(isDone(null)).toBe(false);
  });

  it("returns false for empty object", () => {
    expect(isDone({})).toBe(false);
  });
});
