import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import OpsPage from "@/pages/ops";

const mockGetOpsDashboard = vi.fn();
vi.mock("@/api/ops", () => ({
  getOpsDashboard: (...args: unknown[]) => mockGetOpsDashboard(...args),
}));

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const populatedData = {
  window: { days: 7, from: "2026-06-11T00:00:00Z", to: "2026-06-18T00:00:00Z" },
  run_health: {
    total_runs: 42,
    completed: 35,
    failed: 3,
    cancelled: 2,
    running: 1,
    pending: 1,
    average_duration_s: 292.6,
    slowest_stages: [
      { stage: "adversarial_review", avg_seconds: 1738.7, max_seconds: 1800, samples: 1 },
      { stage: "idea_generation", avg_seconds: 76.8, max_seconds: 172, samples: 3 },
    ],
  },
  model_usage: {
    models: [
      { provider: "openai", served_model: "gpt-4o-2024", calls: 15 },
    ],
    total_receipts: 15,
    warnings: [],
  },
  source_health: {
    papers_found_total: 766,
    zero_result_runs: 3,
    sources: [
      { source: "crossref", papers: 397 },
      { source: "openalex", papers: 309 },
    ],
  },
  quality_trends: {
    proposal_count: 2,
    quality_pass_rate: 93.8,
    common_failures: [
      { failure: "missing citation markers", count: 1 },
    ],
    citation_resolution_rate: 63.6,
    total_citation_needed: 4,
    total_valid_citations: 7,
    remediation_count: 0,
    restore_count: 0,
  },
};

describe("OpsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders title and day selector", () => {
    mockGetOpsDashboard.mockReturnValue(new Promise(() => {}));
    render(<OpsPage />, { wrapper: makeWrapper() });

    expect(screen.getByText("Operational Dashboard")).toBeInTheDocument();
    expect(screen.getByText("7d")).toBeInTheDocument();
    expect(screen.getByText("30d")).toBeInTheDocument();
    expect(screen.getByText("90d")).toBeInTheDocument();
  });

  it("shows loading skeletons while fetching", () => {
    mockGetOpsDashboard.mockReturnValue(new Promise(() => {}));
    render(<OpsPage />, { wrapper: makeWrapper() });

    // Skeletons should be rendered
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders all 4 cards with populated data", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("run-health-card")).toBeInTheDocument();
    });

    expect(screen.getByTestId("model-usage-card")).toBeInTheDocument();
    expect(screen.getByTestId("source-health-card")).toBeInTheDocument();
    expect(screen.getByTestId("quality-trends-card")).toBeInTheDocument();
  });

  it("shows run counts in run health card", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("run-health-card")).toHaveTextContent("42");
    });
    expect(screen.getByTestId("run-health-card")).toHaveTextContent("35");
  });

  it("shows slowest stages", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("slowest-stages")).toBeInTheDocument();
    });
    expect(screen.getByText("adversarial_review")).toBeInTheDocument();
  });

  it("shows model list with call counts", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("model-list")).toBeInTheDocument();
    });
    expect(screen.getByText("openai/gpt-4o-2024")).toBeInTheDocument();
    expect(screen.getByText("15 calls")).toBeInTheDocument();
  });

  it("shows source paper counts", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("source-list")).toBeInTheDocument();
    });
    expect(screen.getByText("crossref")).toBeInTheDocument();
    expect(screen.getByText(/397 papers/)).toBeInTheDocument();
  });

  it("shows quality pass rate", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText("94%")).toBeInTheDocument(); // 93.8 rounded
    });
  });

  it("shows error card on fetch failure", async () => {
    mockGetOpsDashboard.mockRejectedValue(new Error("Network error"));
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Failed to load/)).toBeInTheDocument();
    });
  });

  it("switches time window on day button click", async () => {
    mockGetOpsDashboard.mockResolvedValue(populatedData);
    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("run-health-card")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("30d"));

    expect(mockGetOpsDashboard).toHaveBeenCalledWith(30);
  });

  it("handles empty data gracefully", async () => {
    mockGetOpsDashboard.mockResolvedValue({
      window: { days: 7, from: "...", to: "..." },
      run_health: {
        total_runs: 0, completed: 0, failed: 0, cancelled: 0,
        running: 0, pending: 0, average_duration_s: 0, slowest_stages: [],
      },
      model_usage: { models: [], total_receipts: 0, warnings: ["No data"] },
      source_health: { papers_found_total: 0, zero_result_runs: 0, sources: [] },
      quality_trends: {
        proposal_count: 0, quality_pass_rate: 0, common_failures: [],
        citation_resolution_rate: null, total_citation_needed: 0,
        total_valid_citations: 0, remediation_count: 0, restore_count: 0,
      },
    });

    render(<OpsPage />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText("No data")).toBeInTheDocument(); // warning
    });
  });
});
