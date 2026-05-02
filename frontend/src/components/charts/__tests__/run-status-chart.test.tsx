import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { RunStatusChart } from "@/components/charts/run-status-chart";
import type { PipelineRunSummary } from "@/api/types";

// Mock recharts to avoid canvas/SVG rendering issues in jsdom
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

const sampleRuns: PipelineRunSummary[] = [
  {
    id: 1,
    status: "completed",
    domain: "NLP",
    current_stage: null,
    ideas_count: 5,
    created_at: "2026-05-01T00:00:00Z",
    completed_at: "2026-05-01T01:00:00Z",
    error_message: null,
  },
  {
    id: 2,
    status: "running",
    domain: "CV",
    current_stage: "idea_generation",
    ideas_count: 0,
    created_at: "2026-05-01T00:00:00Z",
    completed_at: null,
    error_message: null,
  },
  {
    id: 3,
    status: "failed",
    domain: "RL",
    current_stage: null,
    ideas_count: 0,
    created_at: "2026-05-01T00:00:00Z",
    completed_at: null,
    error_message: "Timeout",
  },
];

describe("RunStatusChart", () => {
  // ── TEST-11-02-05: Renders with data ────────────────────────────
  it("TEST-11-02-05: renders with data", () => {
    const { container } = render(<RunStatusChart runs={sampleRuns} />);

    // Should render a chart container
    expect(container.querySelector(".recharts-wrapper")).toBeTruthy();
  });

  // ── TEST-11-02-06: Renders empty state (returns null) ───────────
  it("TEST-11-02-06: renders empty state (returns null)", () => {
    const { container } = render(<RunStatusChart runs={[]} />);

    // RunStatusChart returns null when no data
    expect(container.innerHTML).toBe("");
  });
});
