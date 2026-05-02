import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import GapDetailPage from "@/pages/gap-detail";
import type { ResearchGap } from "@/api/types";

// ── JSDOM polyfills for Radix UI ─────────────────────────────────
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

// ── Mock API ─────────────────────────────────────────────────────
vi.mock("@/api/gaps", () => ({
  getGap: vi.fn(),
  listGaps: vi.fn(),
}));

import { getGap, listGaps } from "@/api/gaps";

const mockedGetGap = vi.mocked(getGap);
const mockedListGaps = vi.mocked(listGaps);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderGapDetail(gapId: string = "1") {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/gaps/${gapId}`]}>
        <Routes>
          <Route path="/gaps/:id" element={<GapDetailPage />} />
          <Route path="/gaps" element={<div>Gaps Explorer</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleGap: ResearchGap = {
  id: 1,
  title: "Limited cross-domain evaluation",
  description: "No methods exist for evaluating cross-domain transfer.",
  gap_type: "methodological",
  confidence: 0.85,
  potential_impact: "High",
  idea_count: 3,
  truth: { frequency: 0.75, confidence: 0.82, evidence_count: 5 },
  related_clusters: [1, 3],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedListGaps.mockResolvedValue({ gaps: [], total: 0 });
});

describe("GapDetailPage", () => {
  it("TEST-40-01-01: renders gap title and description", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText("Limited cross-domain evaluation")).toBeInTheDocument();
      expect(screen.getByText(/No methods exist for evaluating/)).toBeInTheDocument();
    });
  });

  it("TEST-40-01-02: gap type badge displays correctly", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText("methodological")).toBeInTheDocument();
    });
  });

  it("TEST-40-01-03: confidence bar renders with percentage", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText(/85% confidence/)).toBeInTheDocument();
    });
  });

  it("TEST-40-01-04: truth values section displays frequency/confidence", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText("Truth Values")).toBeInTheDocument();
      expect(screen.getByText("0.750")).toBeInTheDocument();
      expect(screen.getByText("0.820")).toBeInTheDocument();
      expect(screen.getByText("5")).toBeInTheDocument();
    });
  });

  it("TEST-40-01-05: related ideas section lists linked ideas", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText(/3 ideas linked/)).toBeInTheDocument();
      expect(screen.getByText("View Related Ideas")).toBeInTheDocument();
    });
  });

  it("TEST-40-01-06: cluster membership section displays clusters", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText("Cluster Membership")).toBeInTheDocument();
      expect(screen.getByText("Cluster 1")).toBeInTheDocument();
      expect(screen.getByText("Cluster 3")).toBeInTheDocument();
    });
  });

  it("TEST-40-01-07: back button navigates to /gaps", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText("Back to Gaps")).toBeInTheDocument();
    });
  });

  it("TEST-40-01-08: not-found state shows error for missing gap", async () => {
    mockedGetGap.mockRejectedValue(new Error("Not found"));
    renderGapDetail("999");
    await waitFor(() => {
      expect(screen.getByText("Gap not found")).toBeInTheDocument();
    });
  });

  it("TEST-40-01-09: loading state shows skeleton", () => {
    mockedGetGap.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = renderGapDetail();
    const skeletons = container.querySelectorAll("[class*=\"animate\"]");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("TEST-40-01-10: gap ID displayed in metadata", async () => {
    mockedGetGap.mockResolvedValue({ gap: sampleGap });
    renderGapDetail();
    await waitFor(() => {
      expect(screen.getByText(/Gap ID: 1/)).toBeInTheDocument();
    });
  });
});
