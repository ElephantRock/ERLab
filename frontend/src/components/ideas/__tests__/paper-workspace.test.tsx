/**
 * Phase 1 1E/1F focused tests: PaperWorkspace component.
 *
 * Covers spec 1G frontend cases 3–9 (cases 1–2 are covered by the existing
 * run-config-form tests for the research-question input):
 *   3. Run progress leads to a paper-ready state.        (implicit: ready state renders)
 *   4. The paper workspace renders final content.        (ready state shows paper_md)
 *   5. Proposal and paper are visibly distinguished.     (scope: paper label present)
 *   6. Evaluation scope is correctly labeled.            ("Paper evaluation" + scope badge)
 *   7. Export controls call the correct endpoints.       (exportPaper* called on click)
 *   8. Pending and failed states render correctly.       (pending/failed/not_requested)
 *   9. Empty artifacts cannot appear as successful papers. (empty-md status forced to failed upstream; failed state renders, never ready)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PaperWorkspace } from "@/components/ideas/paper-workspace";
import type { PaperArtifact } from "@/api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// vi.mock factories are hoisted; define the mocks inside the factory and
// re-export via a helper to avoid temporal-dead-zone references.
const exportMocks = {
  exportPaperMarkdown: vi.fn(),
  exportPaperLatex: vi.fn(),
  exportPaperBibtex: vi.fn(),
};
vi.mock("@/api/exports", () => ({
  exportPaperMarkdown: (...args: unknown[]) => exportMocks.exportPaperMarkdown(...args),
  exportPaperLatex: (...args: unknown[]) => exportMocks.exportPaperLatex(...args),
  exportPaperBibtex: (...args: unknown[]) => exportMocks.exportPaperBibtex(...args),
}));

function readyPaper(overrides: Partial<PaperArtifact> = {}): PaperArtifact {
  return {
    status: "ready",
    paper_md: "# Synthesized Full Paper\n\nReal paper body content.",
    title: "Graph-of-Thought Meets Neuro-Symbolic Reasoning",
    word_count: 4347,
    venue: null,
    model_used: "glm-5.1",
    source_count: 10,
    synthesis_strategy: "monolithic",
    generated_at: "2026-07-25T00:00:00Z",
    source_run_id: 1,
    paper_evaluation: {
      status: "ready",
      scope: "paper",
      evaluated_object: "final_paper",
      dimensions: {
        novelty: { score: 0.72, justification: "genuinely novel" },
        rigor: { score: 0.65, justification: "sound" },
        overall: 0.7,
      },
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  exportMocks.exportPaperMarkdown.mockResolvedValue(new Blob(["md"], { type: "text/markdown" }));
  exportMocks.exportPaperLatex.mockResolvedValue(new Blob(["latex"], { type: "text/x-latex" }));
  exportMocks.exportPaperBibtex.mockResolvedValue(new Blob(["bibtex"], { type: "application/x-bibtex" }));
});

describe("PaperWorkspace — state machine", () => {
  it("case 8: not_requested state renders an actionable message", () => {
    render(<PaperWorkspace ideaId={1} paper={null} unresolvedCitationCount={null} />);
    expect(screen.getByText(/No full paper was requested/i)).toBeInTheDocument();
  });

  it("case 8: not_requested status explicitly shows the message", () => {
    render(
      <PaperWorkspace
        ideaId={1}
        paper={{ ...readyPaper(), status: "not_requested", paper_md: null }}
        unresolvedCitationCount={null}
      />,
    );
    expect(screen.getByText(/deep_research/i)).toBeInTheDocument();
  });

  it("case 8: pending state renders a pending message", () => {
    render(
      <PaperWorkspace
        ideaId={1}
        paper={{ ...readyPaper(), status: "pending", paper_md: null }}
        unresolvedCitationCount={null}
      />,
    );
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });

  it("case 8 + 9: failed state renders a failed message (empty paper never appears ready)", () => {
    render(
      <PaperWorkspace
        ideaId={1}
        paper={{ ...readyPaper(), status: "failed", paper_md: null }}
        unresolvedCitationCount={null}
      />,
    );
    expect(screen.getByText(/Paper generation failed/i)).toBeInTheDocument();
    // The ready-content must NOT appear in failed state.
    expect(screen.queryByText(/Synthesized Full Paper/i)).not.toBeInTheDocument();
  });
});

describe("PaperWorkspace — ready state", () => {
  it("case 3 + 4: ready state renders the final paper content", () => {
    render(<PaperWorkspace ideaId={1} paper={readyPaper()} unresolvedCitationCount={0} />);
    expect(screen.getByText("Full Research Paper")).toBeInTheDocument();
    expect(screen.getByText(/Real paper body content/i)).toBeInTheDocument();
    expect(screen.getByText(/4,347 words/i)).toBeInTheDocument();
    expect(screen.getByText(/Ready/i)).toBeInTheDocument();
  });

  it("case 5 + 6: paper evaluation is labeled 'Paper evaluation' with scope: paper, distinct from proposal", () => {
    render(<PaperWorkspace ideaId={1} paper={readyPaper()} unresolvedCitationCount={0} />);
    expect(screen.getByText("Paper Evaluation")).toBeInTheDocument();
    expect(screen.getByText("scope: paper")).toBeInTheDocument();
    expect(screen.getByText(/distinct from the proposal evaluation/i)).toBeInTheDocument();
    // A dimension from the paper evaluation renders.
    expect(screen.getByText("novelty")).toBeInTheDocument();
  });

  it("case 6: a failed paper evaluation does not block viewing the paper", () => {
    render(
      <PaperWorkspace
        ideaId={1}
        paper={{
          ...readyPaper(),
          paper_evaluation: { status: "failed", scope: "paper", error: "evaluator crashed" },
        }}
        unresolvedCitationCount={0}
      />,
    );
    // Paper content still renders.
    expect(screen.getByText(/Real paper body content/i)).toBeInTheDocument();
    // Failure message renders.
    expect(screen.getByText(/Paper evaluation failed/i)).toBeInTheDocument();
  });

  it("case 7: Markdown export calls exportPaperMarkdown with the idea id", async () => {
    render(<PaperWorkspace ideaId={42} paper={readyPaper()} unresolvedCitationCount={0} />);
    const mdBtn = screen.getByRole("button", { name: /Markdown/i });
    fireEvent.click(mdBtn);
    await waitFor(() => {
      expect(exportMocks.exportPaperMarkdown).toHaveBeenCalledWith(42);
    });
  });

  it("case 7: LaTeX export calls exportPaperLatex with the idea id", async () => {
    render(<PaperWorkspace ideaId={42} paper={readyPaper()} unresolvedCitationCount={0} />);
    fireEvent.click(screen.getByRole("button", { name: /LaTeX/i }));
    await waitFor(() => {
      expect(exportMocks.exportPaperLatex).toHaveBeenCalledWith(42);
    });
  });

  it("case 7: BibTeX export calls exportPaperBibtex with the idea id", async () => {
    render(<PaperWorkspace ideaId={42} paper={readyPaper()} unresolvedCitationCount={0} />);
    fireEvent.click(screen.getByRole("button", { name: /BibTeX/i }));
    await waitFor(() => {
      expect(exportMocks.exportPaperBibtex).toHaveBeenCalledWith(42);
    });
  });

  it("citation status: zero unresolved shows an all-resolved message", () => {
    render(<PaperWorkspace ideaId={1} paper={readyPaper()} unresolvedCitationCount={0} />);
    expect(screen.getByText(/All references resolved/i)).toBeInTheDocument();
  });

  it("citation status: nonzero unresolved shows a count", () => {
    render(<PaperWorkspace ideaId={1} paper={readyPaper()} unresolvedCitationCount={3} />);
    expect(screen.getByText(/3 unresolved references/i)).toBeInTheDocument();
  });
});
