import { describe, it, expect, beforeEach, vi } from "vitest";
import { getSessionList } from "@/api/sessions";
import { apiFetchJson } from "@/api/client";

// F1.7a: getSessionList now routes through callContract → apiFetchJson.
vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchUnchecked: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("BATCH-22/TASK-02: Sessions API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls /pipeline/runs/sessions endpoint", async () => {
    const expected = {
      sessions: [
        { session_id: "sess-1", run_count: 3, latest_run_at: "2026-05-02T14:30:00Z" },
      ],
    };
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getSessionList();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/pipeline/runs/sessions",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.sessions).toHaveLength(1);
    expect(result.sessions[0].session_id).toBe("sess-1");
    expect(result.sessions[0].run_count).toBe(3);
  });
});
