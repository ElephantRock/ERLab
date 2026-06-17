import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import GovernancePage from "@/pages/governance";
import * as governanceApi from "@/api/governance";

// ── Mock the API module ──────────────────────────────────────────
vi.mock("@/api/governance", () => ({
  getPending: vi.fn(),
  approveDecision: vi.fn(),
  denyDecision: vi.fn(),
}));

const mockGetPending = vi.mocked(governanceApi.getPending);
const mockApproveDecision = vi.mocked(governanceApi.approveDecision);
const mockDenyDecision = vi.mocked(governanceApi.denyDecision);

// ── Helper ──────────────────────────────────────────────────────
function renderGovernancePage() {
  return render(
    <MemoryRouter initialEntries={["/governance"]}>
      <Routes>
        <Route path="/governance" element={<GovernancePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const samplePending = [
  { id: "gap_001", type: "gap_approval", summary: "Approve gap analysis" },
  { id: "gap_002", type: "cost_review", summary: "Review cost threshold" },
];

describe("BATCH-20/TASK-02: Governance Queue Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-20-02-01: Page renders pending list ──────────────────
  it("TEST-20-02-01: page renders pending approvals from API", async () => {
    mockGetPending.mockResolvedValueOnce({ pending: samplePending });

    renderGovernancePage();

    // Wait for load
    await waitFor(() => {
      expect(screen.getByTestId("governance-list")).toBeInTheDocument();
    });

    expect(screen.getByText("Approve gap analysis")).toBeInTheDocument();
    expect(screen.getByText("Review cost threshold")).toBeInTheDocument();
    expect(screen.getByText("gap_approval")).toBeInTheDocument();
    expect(screen.getByText("cost_review")).toBeInTheDocument();
  });

  // ── TEST-20-02-02: Approve action removes item from list ──────
  it("TEST-20-02-02: approving an item removes it from the list", async () => {
    const user = userEvent.setup();
    mockGetPending.mockResolvedValueOnce({ pending: samplePending });
    mockApproveDecision.mockResolvedValueOnce({
      status: "approved",
      decision_id: "gap_001",
    });

    renderGovernancePage();

    await waitFor(() => {
      expect(screen.getByText("Approve gap analysis")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("approve-btn-gap_001"));

    await waitFor(() => {
      expect(screen.queryByText("Approve gap analysis")).not.toBeInTheDocument();
    });

    // Second item still visible
    expect(screen.getByText("Review cost threshold")).toBeInTheDocument();
    expect(mockApproveDecision).toHaveBeenCalledWith("gap_001");
  });

  // ── TEST-20-02-03: Deny with amendment removes item ────────────
  it("TEST-20-02-03: denying with amendment removes item from list", async () => {
    const user = userEvent.setup();
    mockGetPending.mockResolvedValueOnce({ pending: [samplePending[0]] });
    mockDenyDecision.mockResolvedValueOnce({
      status: "denied",
      decision_id: "gap_001",
      amendment: "Needs revision",
    });

    renderGovernancePage();

    await waitFor(() => {
      expect(screen.getByText("Approve gap analysis")).toBeInTheDocument();
    });

    // Click Deny to reveal amendment input
    await user.click(screen.getByTestId("deny-btn-gap_001"));

    // Type amendment
    const input = screen.getByTestId("amendment-input-gap_001");
    await user.type(input, "Needs revision");

    // Confirm deny
    await user.click(screen.getByTestId("deny-btn-gap_001"));

    await waitFor(() => {
      expect(screen.queryByTestId("approval-card-gap_001")).not.toBeInTheDocument();
    });

    // Empty state should appear
    expect(screen.getByTestId("governance-empty")).toBeInTheDocument();
    expect(mockDenyDecision).toHaveBeenCalledWith("gap_001", "Needs revision");
  });

  // ── TEST-20-02-04: Empty state shows "No pending approvals" ───
  it("TEST-20-02-04: empty state shows message when no pending items", async () => {
    mockGetPending.mockResolvedValueOnce({ pending: [] });

    renderGovernancePage();

    await waitFor(() => {
      expect(screen.getByTestId("governance-empty")).toBeInTheDocument();
    });

    expect(screen.getByText("No pending approvals")).toBeInTheDocument();
  });

  // ── TEST-20-02-05: API error handled gracefully ───────────────
  it("TEST-20-02-05: API error is displayed with error banner", async () => {
    mockGetPending.mockRejectedValueOnce(new Error("Server unreachable"));

    renderGovernancePage();

    await waitFor(() => {
      expect(screen.getByTestId("governance-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Failed to load pending approvals")).toBeInTheDocument();
  });
});
