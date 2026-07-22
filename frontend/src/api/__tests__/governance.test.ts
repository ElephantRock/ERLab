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

import { apiFetchJson, apiFetchUnchecked } from "@/api/client";

const mockApiFetch = vi.mocked(apiFetchUnchecked);
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
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await approveDecision("gap_001");

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/governance/gap_001/approve",
      { method: "POST" },
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
    mockApiFetch.mockResolvedValueOnce(expected);

    const result = await denyDecision("gap_002", "Revise methodology section");

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/governance/gap_002/deny",
      {
        method: "POST",
        body: JSON.stringify({ amendment: "Revise methodology section" }),
      },
    );
    expect(result).toEqual(expected);
  });
});
