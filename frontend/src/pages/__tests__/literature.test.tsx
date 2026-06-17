import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import LiteraturePage from "@/pages/literature";
import type { SearchResponse } from "@/api/literature";

// ── Mock API ─────────────────────────────────────────────────────
vi.mock("@/api/literature", () => ({
  searchLiterature: vi.fn(),
  ingestPaper: vi.fn(),
}));

import { searchLiterature, ingestPaper } from "@/api/literature";

const mockedSearch = vi.mocked(searchLiterature);
const mockedIngest = vi.mocked(ingestPaper);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderLiteraturePage() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LiteraturePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleResponse: SearchResponse = {
  papers: [
    {
      id: "ss-1",
      source: "semantic_scholar",
      title: "Attention Is All You Need",
      abstract: "We propose the Transformer.",
      authors: [{ name: "Ashish Vaswani" }],
      year: 2017,
      venue: "NeurIPS",
      citation_count: 50000,
      url: "https://arxiv.org/abs/1706.03762",
      doi: "10.5555/test",
      arxiv_id: null,
      keywords: [],
    },
    {
      id: "arxiv-2",
      source: "arxiv",
      title: "BERT: Pre-training of Deep Bidirectional Transformers",
      abstract: "We introduce BERT.",
      authors: [{ name: "Jacob Devlin" }],
      year: 2018,
      venue: null,
      citation_count: null,
      url: null,
      doi: null,
      arxiv_id: "1810.04805",
      keywords: [],
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("BATCH-23/TASK-02: LiteraturePage", () => {
  // ── TEST-23-02-01: Literature page renders search input ──
  it("TEST-23-02-01: renders literature search page with search input", () => {
    renderLiteraturePage();

    expect(screen.getByText("Literature Search")).toBeInTheDocument();
    expect(screen.getByTestId("literature-search-input")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Search papers by topic, author, or keyword..."),
    ).toBeInTheDocument();
  });

  // ── TEST-23-02-02: Search returns paper cards ──
  it("TEST-23-02-02: search returns paper cards", async () => {
    const user = userEvent.setup();
    mockedSearch.mockResolvedValue(sampleResponse);

    renderLiteraturePage();

    const input = screen.getByTestId("literature-search-input");
    await user.type(input, "transformer");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText(/2 papers for/)).toBeInTheDocument();
    });

    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    expect(
      screen.getByText("BERT: Pre-training of Deep Bidirectional Transformers"),
    ).toBeInTheDocument();
  });

  // ── TEST-23-02-05: Empty results shows message ──
  it("TEST-23-02-05: empty results shows no results message", async () => {
    const user = userEvent.setup();
    mockedSearch.mockResolvedValue({ papers: [] });

    renderLiteraturePage();

    const input = screen.getByTestId("literature-search-input");
    await user.type(input, "xyznonexistent");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByTestId("no-results")).toBeInTheDocument();
    });

    expect(screen.getByText(/No papers found/)).toBeInTheDocument();
  });

  // ── TEST-23-02-06: Search error handled ──
  it("TEST-23-02-06: search error is handled with error message", async () => {
    const user = userEvent.setup();
    mockedSearch.mockRejectedValue(new Error("Network error"));

    renderLiteraturePage();

    const input = screen.getByTestId("literature-search-input");
    await user.type(input, "test");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByTestId("search-error")).toBeInTheDocument();
    });

    expect(screen.getByText("Search failed. Please try again.")).toBeInTheDocument();
  });
});
