import { describe, it, expect } from "vitest";
import {
  getNoveltyLabel,
  getFeasibilityLabel,
  getScoreColor,
  getScoreBg,
} from "@/lib/score-utils";

describe("getNoveltyLabel", () => {
  it("returns Low for scores below 0.3", () => {
    expect(getNoveltyLabel(0)).toBe("Low");
    expect(getNoveltyLabel(0.29)).toBe("Low");
  });

  it("returns Moderate for scores 0.3–0.59", () => {
    expect(getNoveltyLabel(0.3)).toBe("Moderate");
    expect(getNoveltyLabel(0.5)).toBe("Moderate");
    expect(getNoveltyLabel(0.59)).toBe("Moderate");
  });

  it("returns High for scores 0.6–0.79", () => {
    expect(getNoveltyLabel(0.6)).toBe("High");
    expect(getNoveltyLabel(0.7)).toBe("High");
    expect(getNoveltyLabel(0.79)).toBe("High");
  });

  it("returns Very High for scores >= 0.8", () => {
    expect(getNoveltyLabel(0.8)).toBe("Very High");
    expect(getNoveltyLabel(1.0)).toBe("Very High");
  });
});

describe("getFeasibilityLabel", () => {
  it("returns Difficult for scores below 3", () => {
    expect(getFeasibilityLabel(0)).toBe("Difficult");
    expect(getFeasibilityLabel(2)).toBe("Difficult");
  });

  it("returns Moderate for scores 3–5", () => {
    expect(getFeasibilityLabel(3)).toBe("Moderate");
    expect(getFeasibilityLabel(5)).toBe("Moderate");
  });

  it("returns Feasible for scores 6–7", () => {
    expect(getFeasibilityLabel(6)).toBe("Feasible");
    expect(getFeasibilityLabel(7)).toBe("Feasible");
  });

  it("returns Very Feasible for scores >= 8", () => {
    expect(getFeasibilityLabel(8)).toBe("Very Feasible");
    expect(getFeasibilityLabel(10)).toBe("Very Feasible");
  });
});

describe("getScoreColor", () => {
  it("returns correct color classes for novelty scale", () => {
    expect(getScoreColor(0.1, "novelty")).toBe("text-destructive");
    expect(getScoreColor(0.4, "novelty")).toBe("text-warning");
    expect(getScoreColor(0.7, "novelty")).toBe("text-success");
    expect(getScoreColor(0.9, "novelty")).toBe("text-success");
  });

  it("normalizes feasibility scale (0-10) to 0-1", () => {
    expect(getScoreColor(2, "feasibility")).toBe("text-destructive");
    expect(getScoreColor(5, "feasibility")).toBe("text-warning");
    expect(getScoreColor(7, "feasibility")).toBe("text-success");
    expect(getScoreColor(9, "feasibility")).toBe("text-success");
  });
});

describe("getScoreBg", () => {
  it("returns correct bg classes for novelty scale", () => {
    expect(getScoreBg(0.1, "novelty")).toBe("bg-destructive/10 text-destructive");
    expect(getScoreBg(0.9, "novelty")).toBe("bg-success/10 text-success");
  });

  it("normalizes feasibility scale (0-10) to 0-1", () => {
    expect(getScoreBg(2, "feasibility")).toBe("bg-destructive/10 text-destructive");
    expect(getScoreBg(9, "feasibility")).toBe("bg-success/10 text-success");
  });
});
