import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunCard } from "@/components/pipeline/run-card";
import type { PipelineRunSummary } from "@/api/types";

function makeRun(overrides: Partial<PipelineRunSummary> = {}): PipelineRunSummary {
  return {
    id: 1,
    status: "completed",
    domain: "NLP",
    current_stage: null,
    ideas_count: 5,
    created_at: "2025-01-01T00:00:00Z",
    completed_at: "2025-01-01T00:10:00Z",
    error_message: null,
    ...overrides,
  };
}

describe("RunCard", () => {
  it("renders run ID, domain, and status", () => {
    render(<RunCard run={makeRun()} />);
    expect(screen.getByText(/Run #1/)).toBeInTheDocument();
    expect(screen.getByText("NLP")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("shows ideas count when > 0", () => {
    render(<RunCard run={makeRun({ ideas_count: 5 })} />);
    expect(screen.getByText("5 ideas")).toBeInTheDocument();
  });

  it("hides ideas count when 0", () => {
    render(<RunCard run={makeRun({ ideas_count: 0 })} />);
    expect(screen.queryByText(/ideas/)).not.toBeInTheDocument();
  });

  it("calls onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<RunCard run={makeRun()} onClick={onClick} />);
    await userEvent.click(screen.getByText(/Run #1/));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
