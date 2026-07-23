import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  getCostSummary,
  getCostByProvider,
  getCostByStage,
  getCostByModel,
  getRunCostBreakdown,
} from "@/api/costs";
import type {
  CostSummary,
  ProviderBreakdown,
  StageBreakdown,
  ModelBreakdown,
  RunCostBreakdown,
} from "@/api/costs";
import { apiFetchJson } from "@/api/client";

// F1.7a: all five cost functions now route through callContract → apiFetchJson.
vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("BATCH-18/TASK-01: Cost API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-18-01-01: getCostSummary() calls correct endpoint ──────
  it("TEST-18-01-01: getCostSummary() calls correct endpoint", async () => {
    const expected: CostSummary = {
      total_cost_usd: 1.23,
      total_tokens: 150000,
      event_count: 42,
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getCostSummary();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/costs/summary",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.total_cost_usd).toBe(1.23);
    expect(result.total_tokens).toBe(150000);
    expect(result.event_count).toBe(42);
  });

  // ── TEST-18-01-02: getCostByProvider() returns typed response ───
  it("TEST-18-01-02: getCostByProvider() returns typed response", async () => {
    const expected: ProviderBreakdown = {
      openai: { cost_usd: 0.5, input_tokens: 1000, output_tokens: 500, calls: 10 },
      anthropic: { cost_usd: 0.3, input_tokens: 800, output_tokens: 200, calls: 5 },
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getCostByProvider();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/costs/by-provider",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result.openai.cost_usd).toBe(0.5);
  });

  // ── TEST-18-01-03: getCostByStage() returns typed response ──────
  it("TEST-18-01-03: getCostByStage() returns typed response", async () => {
    const expected: StageBreakdown = {
      generation: { cost_usd: 0.3, input_tokens: 500, output_tokens: 200, calls: 5 },
      novelty_checking: { cost_usd: 0.2, input_tokens: 300, output_tokens: 100, calls: 3 },
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getCostByStage();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/costs/by-stage",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result.generation.calls).toBe(5);
  });

  // ── TEST-18-01-04: getCostByModel() returns typed response ──────
  it("TEST-18-01-04: getCostByModel() returns typed response", async () => {
    const expected: ModelBreakdown = {
      "openai/gpt-4": { cost_usd: 0.8, input_tokens: 1500, output_tokens: 300, calls: 8 },
      "anthropic/claude-3": { cost_usd: 0.4, input_tokens: 600, output_tokens: 150, calls: 4 },
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getCostByModel();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/costs/by-model",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result["openai/gpt-4"].cost_usd).toBe(0.8);
  });

  // ── TEST-18-01-05: getRunCostBreakdown(id) calls /costs/run/{id} ─
  it("TEST-18-01-05: getRunCostBreakdown(id) calls /costs/run/{id}", async () => {
    const expected: RunCostBreakdown = {
      run_id: "run_20260422_143908",
      summary: { total_cost_usd: 0.5, total_tokens: 50000, event_count: 10 },
      by_provider: { openai: { cost_usd: 0.5, input_tokens: 1000, output_tokens: 500, calls: 10 } },
      by_stage: { generation: { cost_usd: 0.3, input_tokens: 500, output_tokens: 200, calls: 5 } },
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getRunCostBreakdown("run_20260422_143908");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/costs/run/run_20260422_143908",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual(expected);
    expect(result.run_id).toBe("run_20260422_143908");
    expect(result.summary.total_cost_usd).toBe(0.5);
    expect(result.by_provider.openai.calls).toBe(10);
    expect(result.by_stage.generation.cost_usd).toBe(0.3);
  });
});
