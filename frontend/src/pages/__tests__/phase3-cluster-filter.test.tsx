/**
 * Phase 3: Gaps Explorer cluster click → filter behavior
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import GapsExplorer from "@/pages/gaps-explorer";
import type { ResearchGap, GapListResponse } from "@/api/types";

// ── Polyfills ──────────────────────────────────────────────────
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView = vi.fn();
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ── Mocks ──────────────────────────────────────────────────────
// F1.3a: gaps-explorer now calls getGapClusters() from @/api/gaps (contract-
// backed via callContract → apiFetchJson) instead of an inline apiFetchUnchecked
// call. Mock the gaps module to provide both listGaps (still used for the main
// list) and getGapClusters (consumed by the clusters tab).
vi.mock("@/api/gaps", () => ({
  listGaps: vi.fn(),
  getGapClusters: vi.fn(),
}));

vi.mock("@/components/gaps/gap-card", () => ({
  GapCard: ({ gap }: { gap: ResearchGap }) => (
    <div data-testid="gap-card">{gap.title}</div>
  ),
}));

vi.mock("@/components/gaps/cluster-scatter", () => ({
  ClusterScatterPlot: ({ onClusterClick, selectedClusterId }: {
    onClusterClick?: (id: number) => void;
    selectedClusterId?: number | null;
  }) => (
    <div data-testid="cluster-scatter">
      <button
        data-testid="cluster-0"
        onClick={() => onClusterClick?.(0)}
      >
        Cluster 0{selectedClusterId === 0 ? " (selected)" : ""}
      </button>
      <button
        data-testid="cluster-1"
        onClick={() => onClusterClick?.(1)}
      >
        Cluster 1{selectedClusterId === 1 ? " (selected)" : ""}
      </button>
    </div>
  ),
}));

import { listGaps, getGapClusters } from "@/api/gaps";

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

const sampleGaps: GapListResponse = {
  gaps: [
    {
      id: 1,
      title: "Gap in transformer scaling",
      description: "Description here",
      gap_type: "methodological",
      confidence: 0.85,
      potential_impact: "High",
    },
  ],
  total: 1,
};

const mockClusters = {
  clusters: [
    { cluster_id: 0, label: "Transformers", paper_count: 15, top_terms: ["attention"], avg_citations: 42 },
    { cluster_id: 1, label: "Diffusion", paper_count: 8, top_terms: ["noise"], avg_citations: 25 },
  ],
  total_papers: 23,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Cluster click → filter behavior", () => {
  it("switches to gaps tab and shows filter badge when cluster clicked", async () => {
    vi.mocked(listGaps).mockResolvedValue(sampleGaps);
    vi.mocked(getGapClusters).mockResolvedValue(mockClusters);

    renderGapsExplorer();

    // Switch to clusters tab
    fireEvent.click(screen.getByText("Clusters"));

    // Wait for cluster mock to render
    await waitFor(() => {
      expect(screen.getByTestId("cluster-scatter")).toBeInTheDocument();
    });

    // Click cluster 0
    fireEvent.click(screen.getByTestId("cluster-0"));

    // Should switch back to gaps tab and show filter badge
    await waitFor(() => {
      expect(screen.getByTestId("cluster-filter-badge")).toBeInTheDocument();
    });
    expect(screen.getByText("Cluster 0")).toBeInTheDocument();
  });

  it("clears cluster filter when Clear button clicked", async () => {
    vi.mocked(listGaps).mockResolvedValue(sampleGaps);
    vi.mocked(getGapClusters).mockResolvedValue(mockClusters);

    renderGapsExplorer();

    // Switch to clusters and click a cluster
    fireEvent.click(screen.getByText("Clusters"));
    await waitFor(() => expect(screen.getByTestId("cluster-scatter")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("cluster-1"));

    await waitFor(() => {
      expect(screen.getByTestId("cluster-filter-badge")).toBeInTheDocument();
    });

    // Click Clear
    fireEvent.click(screen.getByText("Clear"));

    expect(screen.queryByTestId("cluster-filter-badge")).not.toBeInTheDocument();
  });

  it("toggles cluster filter off when same cluster clicked again", async () => {
    vi.mocked(listGaps).mockResolvedValue(sampleGaps);
    vi.mocked(getGapClusters).mockResolvedValue(mockClusters);

    renderGapsExplorer();

    // Click cluster 0
    fireEvent.click(screen.getByText("Clusters"));
    await waitFor(() => expect(screen.getByTestId("cluster-scatter")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("cluster-0"));

    await waitFor(() => {
      expect(screen.getByTestId("cluster-filter-badge")).toBeInTheDocument();
    });

    // Go back to clusters and click same cluster again
    fireEvent.click(screen.getByText("Clusters"));
    await waitFor(() => expect(screen.getByTestId("cluster-scatter")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("cluster-0"));

    // Should toggle off — no filter badge
    await waitFor(() => {
      expect(screen.queryByTestId("cluster-filter-badge")).not.toBeInTheDocument();
    });
  });
});
