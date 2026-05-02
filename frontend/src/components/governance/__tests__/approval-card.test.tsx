import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApprovalCard } from "@/components/governance/approval-card";
import type { PendingApproval } from "@/api/governance";

const sampleItem: PendingApproval = {
  id: "gap_001",
  type: "gap_approval",
  summary: "Approve gap analysis for cross-lingual transfer",
};

const noop = () => Promise.resolve();

describe("BATCH-20/TASK-01: ApprovalCard Component", () => {
  // ── TEST-20-01-04: ApprovalCard renders item with approve/deny buttons ─
  it("TEST-20-01-04: renders item summary, type badge, and approve/deny buttons", () => {
    render(<ApprovalCard item={sampleItem} onApprove={noop} onDeny={noop} />);

    expect(screen.getByText("Approve gap analysis for cross-lingual transfer")).toBeInTheDocument();
    expect(screen.getByText("gap_approval")).toBeInTheDocument();
    expect(screen.getByTestId("approve-btn-gap_001")).toBeInTheDocument();
    expect(screen.getByTestId("deny-btn-gap_001")).toBeInTheDocument();
  });

  // ── TEST-20-01-05: ApprovalCard deny opens amendment input ──────
  it("TEST-20-01-05: clicking Deny reveals amendment text input", async () => {
    const user = userEvent.setup();
    render(<ApprovalCard item={sampleItem} onApprove={noop} onDeny={noop} />);

    // Amendment input should NOT be visible initially
    expect(screen.queryByTestId("amendment-input-gap_001")).not.toBeInTheDocument();

    // Click Deny to reveal amendment input
    await user.click(screen.getByTestId("deny-btn-gap_001"));

    // Amendment input should now be visible
    expect(screen.getByTestId("amendment-input-gap_001")).toBeInTheDocument();
    expect(screen.getByTestId("amendment-input-gap_001")).toHaveAttribute(
      "placeholder",
      "Optional amendment…",
    );

    // Deny button text changes to "Confirm Deny"
    expect(screen.getByTestId("deny-btn-gap_001")).toHaveTextContent("Confirm Deny");
  });
});
