import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import IdeasBrowser from "@/pages/ideas-browser";
import type { IdeaSummary, IdeaListResponse } from "@/api/types";

// ── JSDOM polyfills for Radix UI ─────────────────────────────────
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ── Mock API (AR-03) ─────────────────────────────────────────────
vi.mock("@/api/ideas", () => ({
  listIdeas: vi.fn(),
}));

vi.mock("@/components/ideas/idea-card", () => ({
  IdeaCard: ({ idea }: { idea: IdeaSummary }) => (
    <div data-testid="idea-card">{idea.title}</div>
  ),
}));

import { listIdeas } from "@/api/ideas";

const mockedListIdeas = vi.mocked(listIdeas);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderIdeasBrowser() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <IdeasBrowser />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleIdea: IdeaSummary = {
  id: 1,
  title: "Neural Architecture Search via RL",
  domain: "Deep Learning",
  novelty_score: 0.75,
  feasibility_score: null,
  overall_score: null,
  source_gap_ids: null,
  has_proposal: false,
  pipeline_run_id: null,
  created_at: "2026-05-01T00:00:00Z",
};

const populatedResponse: IdeaListResponse = {
  ideas: [sampleIdea],
  total: 1,
  score_guide: {},
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("IdeasBrowser", () => {
  // ── TEST-11-01-09: Renders idea list ────────────────────────────
  it("TEST-11-01-09: renders idea list when data is available", async () => {
    mockedListIdeas.mockResolvedValue(populatedResponse);

    renderIdeasBrowser();

    await waitFor(() => {
      expect(screen.getByText("Neural Architecture Search via RL")).toBeInTheDocument();
    });
    expect(screen.getByText(/1 idea found/)).toBeInTheDocument();
  });

  // ── TEST-11-01-10: Shows empty state ────────────────────────────
  it("TEST-11-01-10: shows empty state when no ideas", async () => {
    mockedListIdeas.mockResolvedValue({ ideas: [], total: 0, score_guide: {} });

    renderIdeasBrowser();

    await waitFor(() => {
      expect(screen.getByText(/No research ideas yet/)).toBeInTheDocument();
    });
  });

  // ── TEST-11-01-11: Handles API error ────────────────────────────
  it("TEST-11-01-11: handles API error gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    mockedListIdeas.mockRejectedValue(new Error("Server error"));

    renderIdeasBrowser();

    // Header should still render
    expect(screen.getByText("Research Ideas")).toBeInTheDocument();

    consoleSpy.mockRestore();
  });
});
