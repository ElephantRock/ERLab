import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GapCard } from "@/components/gaps/gap-card";
import type { ResearchGap } from "@/api/types";

const sampleGap: ResearchGap = {
  id: 1,
  title: "Lack of cross-lingual transfer methods",
  description: "No methods exist for transferring knowledge between typologically distant languages.",
  gap_type: "methodological",
  confidence: 0.75,
  potential_impact: "High",
  idea_count: 0,
};

describe("GapCard", () => {
  it("renders gap title, description, and type badge", () => {
    render(<GapCard gap={sampleGap} />);
    expect(screen.getByText("Lack of cross-lingual transfer methods")).toBeInTheDocument();
    expect(screen.getByText(/No methods exist/)).toBeInTheDocument();
    expect(screen.getByText("methodological")).toBeInTheDocument();
  });

  it("shows confidence percentage", () => {
    render(<GapCard gap={sampleGap} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("renders confidence bar with correct width", () => {
    const { container } = render(<GapCard gap={sampleGap} />);
    const bar = container.querySelector('[style*="width"]');
    expect(bar).toBeTruthy();
    expect(bar?.getAttribute("style")).toContain("75%");
  });
});
