import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import IdeaDetail from "@/pages/idea-detail";
import type { IdeaDetail as IdeaDetailType } from "@/api/types";

// ── Mock API (AR-03) ─────────────────────────────────────────────
vi.mock("@/api/ideas", () => ({
  getIdea: vi.fn(),
  refineIdea: vi.fn(),
}));

vi.mock("@/components/ideas/score-badge", () => ({
  ScoreBadge: ({ score }: { score: number }) => (
    <span data-testid="score-badge">{score}</span>
  ),
}));

vi.mock("@/components/ideas/export-button", () => ({
  ExportButton: () => <button data-testid="export-btn">Export</button>,
}));

vi.mock("@/components/ideas/feedback-form", () => ({
  FeedbackForm: ({ ideaId }: { ideaId: number }) => (
    <div data-testid="feedback-form">Feedback for {ideaId}</div>
  ),
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

const mockedGetIdea = vi.mocked(getIdea);

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

const sampleIdea: IdeaDetailType = {
  id: 1,
  title: "Quantum NLP for Low-Resource Languages",
  domain: "Quantum Computing + NLP",
  novelty_score: 0.92,
  feasibility_score: 4.5,
  overall_score: 0.68,
  pipeline_run_id: null,
  created_at: "2026-05-01T00:00:00Z",
  problem_statement: "Low-resource languages lack sufficient training data.",
  proposed_method: "Use quantum embeddings for cross-lingual transfer.",
  expected_contributions: "A novel quantum-classical hybrid approach.",
  novelty_report: null,
  feasibility_report: null,
  proposal_md: "# Proposal\n\nThis is the proposal.",
  proposal_latex: null,
  proposal_sections: null,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("IdeaDetail", () => {
  // ── TEST-11-01-12: Renders with valid ID ────────────────────────
  it("TEST-11-01-12: renders idea detail with valid ID", async () => {
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(
        screen.getByText("Quantum NLP for Low-Resource Languages"),
      ).toBeInTheDocument();
    });

    // Domain shown
    expect(screen.getByText("Quantum Computing + NLP")).toBeInTheDocument();

    // Problem statement section
    expect(
      screen.getByText("Low-resource languages lack sufficient training data."),
    ).toBeInTheDocument();

    // Proposed method section
    expect(
      screen.getByText("Use quantum embeddings for cross-lingual transfer."),
    ).toBeInTheDocument();

    // Expected contributions
    expect(
      screen.getByText("A novel quantum-classical hybrid approach."),
    ).toBeInTheDocument();

    // Export button present
    expect(screen.getByTestId("export-btn")).toBeInTheDocument();

    // Feedback form rendered with correct ID
    expect(screen.getByTestId("feedback-form")).toBeInTheDocument();
  });

  // ── TEST-11-01-13: Shows 404 for missing idea ───────────────────
  it("TEST-11-01-13: shows not found for missing idea", async () => {
    mockedGetIdea.mockResolvedValue({ idea: null });

    renderIdeaDetail("9999");

    await waitFor(() => {
      expect(screen.getByText("Idea not found.")).toBeInTheDocument();
    });
  });
});
