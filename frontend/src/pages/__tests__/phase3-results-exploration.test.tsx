/**
 * Phase 3: Results Exploration tests
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// ── Polyfills ──────────────────────────────────────────────────
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

// ── Mocks for IdeaDetail ──────────────────────────────────────
vi.mock("@/api/ideas", () => ({
  getIdea: vi.fn(),
  refineIdea: vi.fn(),
}));

vi.mock("@/components/ideas/score-badge", () => ({
  ScoreBadge: ({ score }: { score: number }) => (
    <span data-testid="score-badge">{score}</span>
  ),
}));

vi.mock("@/components/export/export-dialog", () => ({
  ExportDialog: ({ ideaId }: { ideaId: number }) => (
    <button data-testid="export-btn">Export (Idea {ideaId})</button>
  ),
}));

vi.mock("@/components/ideas/feedback-form", () => ({
  FeedbackForm: ({ ideaId }: { ideaId: number }) => (
    <div data-testid="feedback-form">Feedback for {ideaId}</div>
  ),
}));

vi.mock("@/components/idea/comment-thread", () => ({
  CommentThread: () => <div data-testid="comment-thread" />,
}));

vi.mock("@/components/idea/share-dialog", () => ({
  ShareDialog: () => <div data-testid="share-dialog" />,
}));

vi.mock("@/components/ideas/novelty-report-view", () => ({
  NoveltyReportView: () => <div data-testid="novelty-report" />,
}));

vi.mock("@/components/ideas/feasibility-report-view", () => ({
  FeasibilityReportView: () => <div data-testid="feasibility-report" />,
}));

vi.mock("@/components/markdown/markdown-renderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => (
    <div data-testid="markdown">{content}</div>
  ),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getIdea } from "@/api/ideas";
import IdeaDetail from "@/pages/idea-detail";
import type { IdeaDetail as IdeaDetailType } from "@/api/types";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderIdeaDetail(id: string) {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/ideas/${id}`]}>
        <Routes>
          <Route path="/ideas/:id" element={<IdeaDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const baseIdea: IdeaDetailType = {
  id: 1,
  title: "Test Idea",
  problem_statement: "A problem",
  proposed_method: "A method",
  expected_contributions: "Contributions",
  domain: "Machine Learning",
  novelty_score: 0.8,
  feasibility_score: 0.6,
  overall_score: 0.7,
  source_gap_ids: null,
  has_proposal: false,
  pipeline_run_id: 1,
  created_at: "2026-06-01T00:00:00Z",
  novelty_report: null,
  feasibility_report: null,
  proposal_md: null,
  proposal_latex: null,
  proposal_sections: null,
  mechanical_metrics: null,
  experiment_results: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

// ── experiment_results type tests ──────────────────────────────

describe("experiment_results type", () => {
  it("renders populated experiment_results as array of cards", async () => {
    const idea: IdeaDetailType = {
      ...baseIdea,
      proposal_md: "# Proposal",
      experiment_results: [
        {
          id: 101,
          success: true,
          exit_code: 0,
          execution_time_seconds: 12.5,
          stdout: "All tests passed",
          error: null,
          created_at: "2026-06-15T10:00:00Z",
        },
        {
          id: 102,
          success: false,
          exit_code: 1,
          execution_time_seconds: 3.2,
          stdout: null,
          error: "RuntimeError",
          created_at: "2026-06-15T11:00:00Z",
        },
      ],
    };
    vi.mocked(getIdea).mockResolvedValue({ idea });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText(/Experiments \(2\)/)).toBeInTheDocument();
    });
  });

  it("hides experiments tab when experiment_results is null", async () => {
    vi.mocked(getIdea).mockResolvedValue({ idea: { ...baseIdea, experiment_results: null } });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Test Idea")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Experiments/)).not.toBeInTheDocument();
  });

  it("hides experiments tab when experiment_results is empty array", async () => {
    vi.mocked(getIdea).mockResolvedValue({ idea: { ...baseIdea, experiment_results: [] } });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Test Idea")).toBeInTheDocument();
    });
    expect(screen.queryByText(/Experiments/)).not.toBeInTheDocument();
  });
});

// ── Copy-to-clipboard tests ────────────────────────────────────

describe("Copy-to-clipboard on proposal sections", () => {
  it("renders copy button for each proposal section", async () => {
    const idea: IdeaDetailType = {
      ...baseIdea,
      proposal_md: "# Some proposal",
      proposal_sections: {
        introduction: "This is the introduction.",
        methodology: "This is the methodology.",
      },
    };
    vi.mocked(getIdea).mockResolvedValue({ idea });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Test Idea")).toBeInTheDocument();
    });

    expect(screen.getByTestId("copy-section-introduction")).toBeInTheDocument();
    expect(screen.getByTestId("copy-section-methodology")).toBeInTheDocument();
  });

  it("calls navigator.clipboard.writeText on copy click", async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText: writeTextSpy },
    });

    const idea: IdeaDetailType = {
      ...baseIdea,
      proposal_md: "# Proposal",
      proposal_sections: {
        abstract: "This is the abstract.",
      },
    };
    vi.mocked(getIdea).mockResolvedValue({ idea });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Test Idea")).toBeInTheDocument();
    });

    const copyBtn = screen.getByTestId("copy-section-abstract");
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(writeTextSpy).toHaveBeenCalledWith("This is the abstract.");
    });
  });
});
