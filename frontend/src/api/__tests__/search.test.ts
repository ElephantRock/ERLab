import { describe, it, expect, beforeEach, vi } from "vitest";
import { globalSearch } from "@/api/search";
import { apiFetchJson } from "@/api/client";

// F1.7a: globalSearch now routes through callContract → apiFetchJson.
vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchUnchecked: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("BATCH-48/TASK-02: Search API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls /search/ endpoint with query parameter", async () => {
    const expected = {
      query: "test",
      results: { ideas: { total: 0, items: [] } },
      total: 0,
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await globalSearch("test");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/search/?q=test",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.query).toBe("test");
    expect(result.total).toBe(0);
  });

  it("passes types parameter as comma-separated string", async () => {
    const expected = {
      query: "neural",
      results: {
        ideas: { total: 1, items: [{ id: 1, title: "Idea 1", domain: "ML", overall_score: 0.8 }] },
      },
      total: 1,
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    await globalSearch("neural", ["ideas", "gaps"]);

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/search/?q=neural&types=ideas%2Cgaps",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("omits types parameter when empty array is passed", async () => {
    mockApiFetchJson.mockResolvedValueOnce({ query: "x", results: {}, total: 0 });

    await globalSearch("x", []);

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/search/?q=x",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("omits types parameter when not provided", async () => {
    mockApiFetchJson.mockResolvedValueOnce({ query: "y", results: {}, total: 0 });

    await globalSearch("y");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/search/?q=y",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
