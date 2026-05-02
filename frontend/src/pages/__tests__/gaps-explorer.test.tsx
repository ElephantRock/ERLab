import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import GapsExplorer from "@/pages/gaps-explorer";
import type { ResearchGap, GapListResponse } from "@/api/types";

// ── Mock API (AR-03) ─────────────────────────────────────────────
vi.mock("@/api/gaps", () => ({
  listGaps: vi.fn(),
}));

vi.mock("@/components/gaps/gap-card", () => ({
  GapCard: ({ gap }: { gap: ResearchGap }) => (
    <div data-testid="gap-card">{gap.title}</div>
  ),
}));

import { listGaps } from "@/api/gaps";

const mockedListGaps = vi.mocked(listGaps);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderGapsExplorer() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <GapsExplorer />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleGap: ResearchGap = {
  id: 1,
  title: "Lack of cross-lingual transfer methods",
  description: "No methods exist for transferring knowledge between typologically distant languages.",
  gap_type: "methodological",
  confidence: 0.82,
  potential_impact: "High",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GapsExplorer", () => {
  // ── TEST-11-01-14: Renders gap list ─────────────────────────────
  it("TEST-11-01-14: renders gap list when data is available", async () => {
    const response: GapListResponse = { gaps: [sampleGap], total: 1 };
    mockedListGaps.mockResolvedValue(response);

    renderGapsExplorer();

    await waitFor(() => {
      expect(screen.getByText("Lack of cross-lingual transfer methods")).toBeInTheDocument();
    });
    expect(screen.getByText(/1 gap identified/)).toBeInTheDocument();
  });

  // ── TEST-11-01-15: Shows empty state ────────────────────────────
  it("TEST-11-01-15: shows empty state when no gaps", async () => {
    mockedListGaps.mockResolvedValue({ gaps: [], total: 0 });

    renderGapsExplorer();

    await waitFor(() => {
      expect(
        screen.getByText("No research gaps found. Run a pipeline to discover gaps."),
      ).toBeInTheDocument();
    });
  });
});
