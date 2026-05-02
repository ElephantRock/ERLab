import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { DomainBreakdownChart } from "@/components/charts/domain-breakdown";
import type { IdeaSummary } from "@/api/types";

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

const sampleIdeas: IdeaSummary[] = [
  {
    id: 1,
    title: "Idea A",
    domain: "NLP",
    novelty_score: null,
    feasibility_score: null,
    overall_score: null,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  },
  {
    id: 2,
    title: "Idea B",
    domain: "NLP",
    novelty_score: null,
    feasibility_score: null,
    overall_score: null,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  },
  {
    id: 3,
    title: "Idea C",
    domain: "CV",
    novelty_score: null,
    feasibility_score: null,
    overall_score: null,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  },
];

describe("DomainBreakdownChart", () => {
  // ── TEST-11-02-03: Renders with data ────────────────────────────
  it("TEST-11-02-03: renders with data", () => {
    const { container } = render(<DomainBreakdownChart ideas={sampleIdeas} />);

    // Should render a chart (PieChart with data)
    expect(container.querySelector(".recharts-wrapper")).toBeTruthy();
  });

  // ── TEST-11-02-04: Renders empty state (returns null) ───────────
  it("TEST-11-02-04: renders empty state (returns null)", () => {
    const { container } = render(<DomainBreakdownChart ideas={[]} />);

    // DomainBreakdownChart returns null when no data
    expect(container.innerHTML).toBe("");
  });
});
