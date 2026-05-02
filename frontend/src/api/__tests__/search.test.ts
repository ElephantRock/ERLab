import { describe, it, expect, beforeEach, vi } from "vitest";
import { globalSearch } from "@/api/search";
import { apiFetch } from "@/api/client";

vi.mock("@/api/client", () => ({
  apiFetch: vi.fn(),
}));

const mockApiFetch = vi.mocked(apiFetch);

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
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await globalSearch("test");

    expect(mockApiFetch).toHaveBeenCalledWith("/search/?q=test");
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
    mockApiFetch.mockResolvedValueOnce(expected);

    await globalSearch("neural", ["ideas", "gaps"]);

    expect(mockApiFetch).toHaveBeenCalledWith("/search/?q=neural&types=ideas%2Cgaps");
  });

  it("omits types parameter when empty array is passed", async () => {
    mockApiFetch.mockResolvedValueOnce({ query: "x", results: {}, total: 0 });

    await globalSearch("x", []);

    expect(mockApiFetch).toHaveBeenCalledWith("/search/?q=x");
  });

  it("omits types parameter when not provided", async () => {
    mockApiFetch.mockResolvedValueOnce({ query: "y", results: {}, total: 0 });

    await globalSearch("y");

    expect(mockApiFetch).toHaveBeenCalledWith("/search/?q=y");
  });
});
