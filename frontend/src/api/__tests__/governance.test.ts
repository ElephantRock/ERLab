import { describe, it, expect, beforeEach, vi } from "vitest";
import { getPending, approveDecision, denyDecision } from "@/api/governance";
import type {
  PendingResponse,
  ApproveResponse,
  DenyResponse,
} from "@/api/governance";

vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
  apiFetchJson: vi.fn(),
}));

import { apiFetchJson } from "@/api/client";

const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("BATCH-20/TASK-01: Governance API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-20-01-01: getPending() calls correct endpoint ──────────
  it("TEST-20-01-01: getPending() calls correct endpoint", async () => {
    const expected: PendingResponse = {
      pending: [
        { id: "gap_001", type: "gap_approval", summary: "Approve gap analysis" },
        { id: "gap_002", type: "cost_review", summary: "Review cost threshold" },
      ],
    };
    // F1.3a: getPending now uses callContract → apiFetchJson
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getPending();

    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result).toEqual(expected);
    expect(result.pending).toHaveLength(2);
    expect(result.pending[0].id).toBe("gap_001");
    expect(result.pending[1].type).toBe("cost_review");
  });

  // ── TEST-20-01-02: approveDecision(id) calls POST approve ──────
  it("TEST-20-01-02: approveDecision(id) calls POST approve", async () => {
    const expected: ApproveResponse = {
      status: "approved",
      decision_id: "gap_001",
    };
    // F1.7a: approveDecision now uses callContract → apiFetchJson
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await approveDecision("gap_001");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/governance/gap_001/approve",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result).toEqual(expected);
  });

  // ── TEST-20-01-03: denyDecision(id, amendment) calls POST deny ──
  it("TEST-20-01-03: denyDecision(id, amendment) calls POST deny with body", async () => {
    const expected: DenyResponse = {
      status: "denied",
      decision_id: "gap_002",
      amendment: "Revise methodology section",
    };
    // F1.7a: denyDecision now uses callContract → apiFetchJson
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await denyDecision("gap_002", "Revise methodology section");

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/governance/gap_002/deny",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ amendment: "Revise methodology section" }),
      }),
    );
    expect(result).toEqual(expected);
  });
});
