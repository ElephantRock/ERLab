import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import IdeaDetail from "@/pages/idea-detail";
import type { IdeaDetail as IdeaDetailType } from "@/api/types";

// ── Mock API ─────────────────────────────────────────────────────
vi.mock("@/api/ideas", () => ({
  getIdea: vi.fn(),
  refineIdea: vi.fn(),
  refineSection: vi.fn(),
  getSectionRevisions: vi.fn(),
  restoreSection: vi.fn(),
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
  CommentThread: ({ ideaId }: { ideaId: number }) => (
    <div data-testid="comment-thread">Comments for {ideaId}</div>
  ),
}));

vi.mock("@/components/idea/share-dialog", () => ({
  ShareDialog: ({ ideaId }: { ideaId: number }) => (
    <div data-testid="share-dialog">Share {ideaId}</div>
  ),
}));

vi.mock("@/components/ideas/governance-panel", () => ({
  GovernancePanel: ({ ideaId }: { ideaId: number }) => (
    <div data-testid="governance-panel">Governance {ideaId}</div>
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

import { getIdea, getSectionRevisions } from "@/api/ideas";

const mockedGetIdea = vi.mocked(getIdea);
const mockedGetRevisions = vi.mocked(getSectionRevisions);

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
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
  quality_checks: null,
  section_hashes: null,
  remediation_hints: null,
  citation_audit: null,
  source_gap_ids: null,
  source_gaps: null,
  supporting_papers: null,
  proposal_references: null,
  mechanical_metrics: null,
  experiment_results: null,
  has_proposal: true,
} as IdeaDetailType;

beforeEach(() => { vi.clearAllMocks(); });

describe("IdeaDetail — Proposal Review Workspace", () => {
  it("renders title and domain", async () => {
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Quantum NLP for Low-Resource Languages")).toBeInTheDocument();
    });
    expect(screen.getByText("Quantum Computing + NLP")).toBeInTheDocument();
  });

  it("renders export and refine buttons", async () => {
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("export-btn")).toBeInTheDocument();
    });
    expect(screen.getByText("Refine")).toBeInTheDocument();
  });

  it("renders feedback form", async () => {
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("feedback-form")).toBeInTheDocument();
    });
  });

  it("renders review sidebar with quality and governance sections", async () => {
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("review-sidebar")).toBeInTheDocument();
    });
    expect(screen.getByText("Quality Checks")).toBeInTheDocument();
    expect(screen.getByTestId("governance-panel")).toBeInTheDocument();
  });

  it("shows not found for missing idea", async () => {
    mockedGetIdea.mockResolvedValue({ idea: null });
    renderIdeaDetail("9999");

    await waitFor(() => {
      expect(screen.getByText("Idea not found.")).toBeInTheDocument();
    });
  });

  it("renders back to results button", async () => {
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("back-to-ideas")).toBeInTheDocument();
    });
  });

  // ── Section refinement wiring ────────────────────────────────

  const ideaWithSections: IdeaDetailType = {
    ...sampleIdea,
    proposal_sections: {
      introduction: "This is the introduction with enough words to pass the check.",
      abstract: "Short.",
    },
    section_hashes: {
      introduction: "hash_intro_abc",
      abstract: "hash_abs_def",
    },
    quality_checks: [
      {
        section: "introduction",
        label: "Introduction",
        present: true,
        word_count: 100,
        min_words: 50,
        meets_word_count: true,
        checks: [],
        passed: true,
        failures: [],
      },
      {
        section: "abstract",
        label: "Abstract",
        present: true,
        word_count: 1,
        min_words: 50,
        meets_word_count: false,
        checks: [],
        passed: false,
        failures: ["insufficient word count (1/50)"],
      },
    ],
    remediation_hints: [
      {
        section: "abstract",
        label: "Abstract",
        issue_type: "word_count",
        severity: "error",
        message: "Abstract has only 1 word (min 50)",
        suggestion: "Expand the abstract",
        refinement_available: true,
      },
    ],
  } as IdeaDetailType;

  it("shows fix section button on failing section with refinement available", async () => {
    mockedGetIdea.mockResolvedValue({ idea: ideaWithSections });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("fix-button-abstract")).toBeInTheDocument();
    });
  });

  it("does NOT show fix section button on passing section", async () => {
    mockedGetIdea.mockResolvedValue({ idea: ideaWithSections });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("revision-toggle-introduction")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("fix-button-introduction")).not.toBeInTheDocument();
  });

  it("shows revision history toggle on sections with hashes", async () => {
    mockedGetIdea.mockResolvedValue({ idea: ideaWithSections });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("revision-toggle-introduction")).toBeInTheDocument();
      expect(screen.getByTestId("revision-toggle-abstract")).toBeInTheDocument();
    });
  });

  it("expands revision history drawer on toggle click", async () => {
    mockedGetIdea.mockResolvedValue({ idea: ideaWithSections });
    mockedGetRevisions.mockResolvedValue({
      revisions: [],
      synthetic_original: null,
      current_hash: "hash_intro_abc",
    });

    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByTestId("revision-toggle-introduction")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("revision-drawer-introduction")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("revision-toggle-introduction"));

    await waitFor(() => {
      expect(screen.getByTestId("revision-drawer-introduction")).toBeInTheDocument();
    });
  });

  it("shows quality summary in review sidebar with issues", async () => {
    mockedGetIdea.mockResolvedValue({ idea: ideaWithSections });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("1/2")).toBeInTheDocument();
    });
  });

  it("shows remediation hints in review sidebar", async () => {
    mockedGetIdea.mockResolvedValue({ idea: ideaWithSections });
    renderIdeaDetail("1");

    await waitFor(() => {
      expect(screen.getByText("Remediation Hints")).toBeInTheDocument();
    });
    expect(screen.getByText(/Abstract has only 1 word/)).toBeInTheDocument();
  });
});
