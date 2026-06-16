import { describe, it, expect } from "vitest";
import { PIPELINE_STAGES, API_PREFIX } from "@/lib/constants";

describe("PIPELINE_STAGES", () => {
  it("has 10 stages", () => {
    expect(PIPELINE_STAGES).toHaveLength(10);
  });

  it("each stage has key, label, and icon", () => {
    for (const stage of PIPELINE_STAGES) {
      expect(stage).toHaveProperty("key");
      expect(stage).toHaveProperty("label");
      expect(stage).toHaveProperty("icon");
      expect(typeof stage.key).toBe("string");
      expect(typeof stage.label).toBe("string");
    }
  });

  it("has unique keys", () => {
    const keys = PIPELINE_STAGES.map((s) => s.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});

describe("API_PREFIX", () => {
  it("is /api/v1", () => {
    expect(API_PREFIX).toBe("/api/v1");
  });
});
