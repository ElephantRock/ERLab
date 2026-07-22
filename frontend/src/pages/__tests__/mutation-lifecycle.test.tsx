/**
 * F1.4 — Mutation lifecycle adversarial tests.
 *
 * Proves that critical mutations have truthful pending, duplicate prevention,
 * success/failure surfacing, and cache invalidation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import React from "react";

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderWithProviders(ui: React.ReactElement, initialPath = "/", routePattern?: string) {
  const qc = makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path={routePattern || initialPath} element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── Literature ingest lifecycle (H5) ─────────────────────────────────

vi.mock("@/api/literature", () => ({
  searchLiterature: vi.fn(),
  ingestPaper: vi.fn(),
}));

import { searchLiterature, ingestPaper } from "@/api/literature";

// Mock page-internal components that use @/ alias internally
vi.mock("@/components/literature/paper-card", () => ({
  PaperCard: ({ paper, onIngest, isIngesting, ingestError }: any) => {
    const [confirming, setConfirming] = React.useState(false);
    return (
      <div data-testid={`paper-${paper.id}`}>
        <span>{paper.title}</span>
        {ingestError && <span data-testid="ingest-error">{ingestError}</span>}
        <button
          data-testid="ingest-button"
          disabled={isIngesting}
          onClick={() => {
            if (!confirming) { setConfirming(true); return; }
            onIngest(paper);
            setConfirming(false);
          }}
        >
          {isIngesting ? "Ingesting..." : confirming ? "Confirm Ingest" : "Ingest"}
        </button>
      </div>
    );
  },
}));

vi.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input {...props} />,
}));
vi.mock("@/components/ui/skeleton", () => ({
  Skeleton: (props: any) => <div {...props} />,
}));
vi.mock("@/components/ui/error-card", () => ({
  ErrorCard: ({ message }: any) => <div data-testid="error-card">{message}</div>,
}));
vi.mock("@/components/ui/empty-state", () => ({
  EmptyState: ({ message }: any) => <div>{message}</div>,
}));
vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

import LiteraturePage from "../literature";

describe("Literature ingest lifecycle (F1.4.1)", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("ingest enters pending state with button disabled", async () => {
    vi.mocked(searchLiterature).mockResolvedValue({
      papers: [{
        id: "ss-1", source: "semantic_scholar", title: "Test Paper",
        abstract: "Summary", authors: [{ name: "Author" }], year: 2024,
        venue: "ICML", citation_count: 5, url: null, doi: null,
        arxiv_id: null, keywords: [],
      }],
    });

    // Never resolves — keeps mutation in pending state
    vi.mocked(ingestPaper).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<LiteraturePage />);

    // Search
    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "attention" } });
    fireEvent.submit(input.closest("form")!);

    // Wait for paper card to render
    await waitFor(() => {
      expect(screen.getByText("Test Paper")).toBeInTheDocument();
    });

    // Click Ingest → Confirm
    screen.getByTestId("ingest-button").click();
    await waitFor(() => {
      expect(screen.getByText("Confirm Ingest")).toBeInTheDocument();
    });
    screen.getByTestId("ingest-button").click();

    // Button should show pending state
    await waitFor(() => {
      expect(screen.getByTestId("ingest-button")).toHaveTextContent("Ingesting");
    });
    expect(screen.getByTestId("ingest-button")).toBeDisabled();
  });

  it("ingest failure shows error and allows retry", async () => {
    vi.mocked(searchLiterature).mockResolvedValue({
      papers: [{
        id: "ss-1", source: "semantic_scholar", title: "Fail Paper",
        abstract: "Summary", authors: [{ name: "Author" }], year: 2024,
        venue: null, citation_count: null, url: null, doi: null,
        arxiv_id: null, keywords: [],
      }],
    });

    // First call fails, second succeeds
    vi.mocked(ingestPaper).mockRejectedValueOnce(new Error("Network"));
    vi.mocked(ingestPaper).mockResolvedValueOnce({ status: "ingested", id: "ss-1" });

    renderWithProviders(<LiteraturePage />);

    // Search
    const input2 = screen.getByTestId("literature-search-input") as HTMLInputElement;
    fireEvent.change(input2, { target: { value: "test" } });
    fireEvent.submit(input2.closest("form")!);

    await waitFor(() => {
      expect(screen.getByText("Fail Paper")).toBeInTheDocument();
    });

    // Confirm + Ingest
    screen.getByTestId("ingest-button").click();
    await waitFor(() => screen.getByText("Confirm Ingest"));
    screen.getByTestId("ingest-button").click();

    // Wait for error
    await waitFor(() => {
      expect(screen.getByTestId("ingest-error")).toBeInTheDocument();
    });

    // Retry should be possible (button re-enabled)
    await waitFor(() => {
      expect(screen.getByTestId("ingest-button")).not.toBeDisabled();
    });
  });
});

// ── Gap status mutation lifecycle (M8) ────────────────────────────────

vi.mock("@/api/gaps", () => ({
  getGap: vi.fn(),
  updateGapStatus: vi.fn(),
  submitGapFeedback: vi.fn(),
  asGapStatus: (v: string) =>
    (["identified", "investigating", "addressed"] as readonly string[]).includes(v) ? v as any : null,
  GAP_STATUSES: ["identified", "investigating", "addressed"],
}));

vi.mock("@/api/clients/gap-papers-client", () => ({
  getGapPapers: vi.fn(),
}));

vi.mock("@/components/gaps/gap-feedback-form", () => ({
  GapFeedbackForm: () => <div data-testid="feedback-form" />,
}));

import { getGap, updateGapStatus } from "@/api/gaps";
import { getGapPapers } from "@/api/clients/gap-papers-client";

// Mount the production GapDetailPage
import GapDetailPage from "../gap-detail";

describe("Gap status mutation lifecycle (F1.4.2)", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("same-status selection sends zero requests", async () => {
    vi.mocked(getGap).mockResolvedValue({
      gap: {
        id: 12, title: "Test Gap", description: "desc", gap_type: "methodological",
        confidence: 0.9, potential_impact: "high", idea_count: 0, status: "identified",
      } as any,
    });
    vi.mocked(getGapPapers).mockResolvedValue({ papers: [], total: 0 });
    vi.mocked(updateGapStatus).mockResolvedValue({ gap: { id: 12, status: "identified" } });

    renderWithProviders(<GapDetailPage />, "/gaps/12", "/gaps/:id");

    // Wait for the gap to load
    await waitFor(() => {
      expect(screen.getByText("Test Gap")).toBeInTheDocument();
    });

    // Select the SAME status (identified → identified)
    const select = screen.getByTestId("gap-status-select");
    select.value = "identified";
    select.dispatchEvent(new Event("change", { bubbles: true }));

    // updateGapStatus should NOT be called for same-status
    expect(vi.mocked(updateGapStatus)).not.toHaveBeenCalled();
  });

  it("status select is disabled while mutation is pending", async () => {
    vi.mocked(getGap).mockResolvedValue({
      gap: {
        id: 12, title: "Pending Gap", description: "desc", gap_type: "methodological",
        confidence: 0.9, potential_impact: "high", idea_count: 0, status: "identified",
      } as any,
    });
    vi.mocked(getGapPapers).mockResolvedValue({ papers: [], total: 0 });

    // Never resolves — keeps mutation pending
    vi.mocked(updateGapStatus).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<GapDetailPage />, "/gaps/12", "/gaps/:id");

    await waitFor(() => {
      expect(screen.getByText("Pending Gap")).toBeInTheDocument();
    });

    // Change status to investigating
    const select = screen.getByTestId("gap-status-select");
    select.value = "investigating";
    select.dispatchEvent(new Event("change", { bubbles: true }));

    // Wait for pending indicator
    await waitFor(() => {
      expect(screen.getByTestId("status-pending")).toBeInTheDocument();
    });

    // Select should be disabled during pending
    expect(screen.getByTestId("gap-status-select")).toBeDisabled();
  });

  it("successful status change invalidates the gap query", async () => {
    vi.mocked(getGap).mockResolvedValue({
      gap: {
        id: 12, title: "Invalidate Gap", description: "desc", gap_type: "methodological",
        confidence: 0.9, potential_impact: "high", idea_count: 0, status: "identified",
      } as any,
    });
    vi.mocked(getGapPapers).mockResolvedValue({ papers: [], total: 0 });
    vi.mocked(updateGapStatus).mockResolvedValue({ gap: { id: 12, status: "investigating" } });

    renderWithProviders(<GapDetailPage />, "/gaps/12", "/gaps/:id");

    await waitFor(() => {
      expect(screen.getByText("Invalidate Gap")).toBeInTheDocument();
    });

    // Change status
    const select = screen.getByTestId("gap-status-select");
    select.value = "investigating";
    select.dispatchEvent(new Event("change", { bubbles: true }));

    // Wait for mutation to complete + invalidation
    await waitFor(() => {
      expect(vi.mocked(updateGapStatus)).toHaveBeenCalledWith(12, "investigating");
    });

    // getGap was called again (invalidation triggers refetch)
    await waitFor(() => {
      expect(vi.mocked(getGap).mock.calls.length).toBeGreaterThanOrEqual(2);
    });
  });
});
