import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import KnowledgeSearch from "@/pages/knowledge-search";
import type { KnowledgeSearchResponse } from "@/api/types";

// ── Mock API (AR-03) ─────────────────────────────────────────────
vi.mock("@/api/knowledge", () => ({
  searchKnowledge: vi.fn(),
  getKnowledgeStats: vi.fn().mockResolvedValue({ total_documents: 0, total_chunks: 0 }),
}));

import { searchKnowledge } from "@/api/knowledge";

const mockedSearchKnowledge = vi.mocked(searchKnowledge);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderKnowledgeSearch() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <KnowledgeSearch />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleResponse: KnowledgeSearchResponse = {
  query: "transformer attention",
  results: [
    {
      id: "doc-1",
      text: "Attention is all you need. Transformer architecture overview.",
      metadata: { source: "arxiv", year: "2017", authors: "Vaswani et al." },
      distance: 0.15,
    },
    {
      id: "doc-2",
      text: "Multi-head attention allows the model to jointly attend to information.",
      metadata: { source: "neurips", year: "2017" },
      distance: 0.42,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("KnowledgeSearch", () => {
  // ── TEST-11-01-16: Renders search form ──────────────────────────
  it("TEST-11-01-16: renders search form", () => {
    renderKnowledgeSearch();

    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search papers, methods, findings...")).toBeInTheDocument();
  });

  // ── TEST-11-01-17: Shows search results ─────────────────────────
  it("TEST-11-01-17: shows search results after submission", async () => {
    const user = userEvent.setup();
    mockedSearchKnowledge.mockResolvedValue(sampleResponse);

    renderKnowledgeSearch();

    const input = screen.getByPlaceholderText("Search papers, methods, findings...");
    await user.type(input, "transformer attention");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText(/2 results for/)).toBeInTheDocument();
    });

    // First result text is rendered
    expect(
      screen.getByText("Attention is all you need. Transformer architecture overview."),
    ).toBeInTheDocument();

    // Badges — source badge is unique
    expect(screen.getByText("arxiv")).toBeInTheDocument();
    // Year "2017" appears in both results
    expect(screen.getAllByText("2017").length).toBe(2);
  });
});
