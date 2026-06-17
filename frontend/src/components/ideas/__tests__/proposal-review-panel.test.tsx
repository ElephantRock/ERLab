import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ProposalReviewPanel } from "@/components/ideas/proposal-review-panel";
import type { EnsembleReview } from "@/api/types";

function renderPanel(props: { proposalSections: Record<string, unknown> | null }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProposalReviewPanel {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const mockReview: EnsembleReview = {
  overall_score: 0.82,
  methodology: {
    perspective: "methodology",
    score: 0.85,
    strengths: ["Rigorous experimental design", "Clear ablation study plan"],
    weaknesses: ["Sample size may be insufficient"],
    suggestions: ["Consider larger evaluation datasets"],
  },
  novelty: {
    perspective: "novelty",
    score: 0.78,
    strengths: ["Novel attention mechanism", "Addresses understudied problem"],
    weaknesses: ["Similar to existing sparse attention"],
    suggestions: ["Clarify differentiation from prior work"],
  },
  clarity: {
    perspective: "clarity",
    score: 0.83,
    strengths: ["Well-structured proposal", "Clear problem statement"],
    weaknesses: ["Some notation unclear"],
    suggestions: ["Add notation table"],
  },
  consensus_strengths: ["Strong methodology", "Clear writing"],
  critical_weaknesses: ["Limited evaluation plan", "Missing baseline comparisons"],
  actionable_suggestions: ["Add 3 more baselines", "Include error bars in results"],
  summary: "A strong proposal with sound methodology. Needs broader evaluation.",
};

describe("ProposalReviewPanel", () => {
  it("renders with full ensemble review data", () => {
    renderPanel({
      proposalSections: { abstract: "...", ensemble_review: mockReview },
    });

    expect(screen.getByTestId("proposal-review-panel")).toBeInTheDocument();
    expect(screen.getByTestId("review-overall-score")).toHaveTextContent("82");
    expect(screen.getByTestId("review-summary")).toBeInTheDocument();
  });

  it("shows perspective scores (methodology, novelty, clarity)", () => {
    renderPanel({
      proposalSections: { ensemble_review: mockReview },
    });

    expect(screen.getByText("Methodology")).toBeInTheDocument();
    expect(screen.getByText("Novelty")).toBeInTheDocument();
    expect(screen.getByText("Clarity")).toBeInTheDocument();
  });

  it("shows consensus strengths", () => {
    renderPanel({
      proposalSections: { ensemble_review: mockReview },
    });

    const strengths = screen.getByTestId("review-strengths");
    expect(strengths).toBeInTheDocument();
    expect(screen.getByText("Strong methodology")).toBeInTheDocument();
  });

  it("shows critical weaknesses", () => {
    renderPanel({
      proposalSections: { ensemble_review: mockReview },
    });

    const weaknesses = screen.getByTestId("review-weaknesses");
    expect(weaknesses).toBeInTheDocument();
    expect(screen.getByText("Limited evaluation plan")).toBeInTheDocument();
  });

  it("shows actionable suggestions", () => {
    renderPanel({
      proposalSections: { ensemble_review: mockReview },
    });

    const suggestions = screen.getByTestId("review-suggestions");
    expect(suggestions).toBeInTheDocument();
    expect(screen.getByText("Add 3 more baselines")).toBeInTheDocument();
  });

  it("shows summary text", () => {
    renderPanel({
      proposalSections: { ensemble_review: mockReview },
    });

    expect(screen.getByTestId("review-summary")).toHaveTextContent("A strong proposal");
  });

  it("shows EmptyState when no proposal exists", () => {
    renderPanel({ proposalSections: null });

    expect(screen.getByTestId("proposal-review-panel")).toBeInTheDocument();
    expect(screen.getByText("No proposal synthesized")).toBeInTheDocument();
  });

  it("shows EmptyState when proposal exists but no ensemble review", () => {
    renderPanel({ proposalSections: { abstract: "some text" } });

    expect(screen.getByTestId("proposal-review-panel")).toBeInTheDocument();
    expect(screen.getByText("No review data")).toBeInTheDocument();
  });

  it("handles review with null perspectives gracefully", () => {
    const partial: EnsembleReview = {
      ...mockReview,
      methodology: null,
      clarity: null,
    };
    renderPanel({
      proposalSections: { ensemble_review: partial },
    });

    // Only Novelty should show
    expect(screen.getByText("Novelty")).toBeInTheDocument();
    expect(screen.queryByText("Methodology")).not.toBeInTheDocument();
    expect(screen.queryByText("Clarity")).not.toBeInTheDocument();
  });

  it("handles review with empty lists gracefully", () => {
    const emptyLists: EnsembleReview = {
      ...mockReview,
      consensus_strengths: [],
      critical_weaknesses: [],
      actionable_suggestions: [],
    };
    renderPanel({
      proposalSections: { ensemble_review: emptyLists },
    });

    expect(screen.queryByTestId("review-strengths")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-weaknesses")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-suggestions")).not.toBeInTheDocument();
  });

  it("handles review with empty summary", () => {
    const noSummary: EnsembleReview = {
      ...mockReview,
      summary: "",
    };
    renderPanel({
      proposalSections: { ensemble_review: noSummary },
    });

    expect(screen.queryByTestId("review-summary")).not.toBeInTheDocument();
  });

  it("displays score color coding for high score", () => {
    const highScore: EnsembleReview = {
      ...mockReview,
      overall_score: 0.9,
    };
    renderPanel({
      proposalSections: { ensemble_review: highScore },
    });

    const scoreEl = screen.getByTestId("review-overall-score");
    expect(scoreEl).toHaveTextContent("90");
    expect(scoreEl.className).toContain("text-success");
  });

  it("displays score color coding for low score", () => {
    const lowScore: EnsembleReview = {
      ...mockReview,
      overall_score: 0.3,
    };
    renderPanel({
      proposalSections: { ensemble_review: lowScore },
    });

    const scoreEl = screen.getByTestId("review-overall-score");
    expect(scoreEl).toHaveTextContent("30");
    expect(scoreEl.className).toContain("text-destructive");
  });
});
