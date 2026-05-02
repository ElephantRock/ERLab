import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { ScoreDistributionChart } from "@/components/charts/score-distribution";
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
    novelty_score: 0.85,
    feasibility_score: 8,
    overall_score: null,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  },
  {
    id: 2,
    title: "Idea B",
    domain: "CV",
    novelty_score: 0.4,
    feasibility_score: 3,
    overall_score: null,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  },
  {
    id: 3,
    title: "Idea C",
    domain: "RL",
    novelty_score: 0.15,
    feasibility_score: 1,
    overall_score: null,
    pipeline_run_id: null,
    created_at: "2026-05-01T00:00:00Z",
  },
];

describe("ScoreDistributionChart", () => {
  // ── TEST-11-02-01: Renders with data ────────────────────────────
  it("TEST-11-02-01: renders with data", () => {
    const { container } = render(<ScoreDistributionChart ideas={sampleIdeas} />);

    // Should render a chart container (recharts BarChart)
    expect(container.querySelector(".recharts-wrapper")).toBeTruthy();
  });

  // ── TEST-11-02-02: Renders empty state without crashing ────────
  it("TEST-11-02-02: renders empty state without crashing", () => {
    const { container } = render(<ScoreDistributionChart ideas={[]} />);

    // Should still render the chart container (bars will be zero-height)
    expect(container.querySelector(".recharts-wrapper")).toBeTruthy();
  });
});
