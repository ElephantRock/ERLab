import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScoreBadge } from "@/components/ideas/score-badge";

describe("ScoreBadge", () => {
  it("renders novelty score with label", () => {
    const { container } = render(<ScoreBadge score={0.85} scale="novelty" />);
    expect(container.textContent).toContain("0.85");
    expect(container.textContent).toContain("Very High");
  });

  it("renders feasibility score with /10 format", () => {
    const { container } = render(<ScoreBadge score={7} scale="feasibility" />);
    expect(container.textContent).toContain("7/10");
    expect(container.textContent).toContain("Feasible");
  });

  it("applies green background for high novelty score", () => {
    const { container } = render(<ScoreBadge score={0.9} scale="novelty" />);
    const span = container.querySelector("span");
    expect(span?.className).toContain("bg-green-100");
  });

  it("applies amber background for moderate feasibility score", () => {
    const { container } = render(<ScoreBadge score={5} scale="feasibility" />);
    const span = container.querySelector("span");
    expect(span?.className).toContain("bg-amber-100");
  });
});
