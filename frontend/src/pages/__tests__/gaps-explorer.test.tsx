import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import GapsExplorer from "@/pages/gaps-explorer";
import type { ResearchGap, GapListResponse } from "@/api/types";

// ── JSDOM polyfills for Radix UI (BATCH-39) ────────────────────
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
class IntersectionObserverMock { observe() {} unobserve() {} disconnect() {} }
global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;
Element.prototype.scrollIntoView = vi.fn();
Element.prototype.getBoundingClientRect = vi.fn(() => ({
  width: 0, height: 0, x: 0, y: 0, top: 0, left: 0, bottom: 0, right: 0,
}));
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

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
    expect(screen.getByText(/1 gap/)).toBeInTheDocument();
  });

  // ── TEST-11-01-15: Shows empty state ────────────────────────────
  it("TEST-11-01-15: shows empty state when no gaps", async () => {
    mockedListGaps.mockResolvedValue({ gaps: [], total: 0 });

    renderGapsExplorer();

    await waitFor(() => {
      expect(
        screen.getByText(/No research gaps found/),
      ).toBeInTheDocument();
    });
  });
});
