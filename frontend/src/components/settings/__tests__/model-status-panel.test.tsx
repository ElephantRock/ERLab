/**
 * Tests for ModelStatusPanel
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ModelStatusPanel } from "@/components/settings/model-status-panel";

vi.mock("@/api/settings", () => ({
  getCatalog: vi.fn(),
  getAssignments: vi.fn(),
}));

import { getCatalog, getAssignments } from "@/api/settings";

const mockCatalog = {
  models: [
    {
      model_id: "qwen3-4b",
      display_name: "Qwen3 4B",
      provider_type: "lmstudio",
      endpoint_url: "http://localhost:1234",
      parameter_count: "4B",
      context_length: 262144,
      context_label: "262K",
      quantization: "Q4_K_M",
      size_gb: 2.5,
      capabilities: { json_mode: true, tools: false, vision: false, thinking: true },
      is_loaded: true,
      health_status: "healthy",
      measured: { total_calls: 10, reliability: 1.0, json_reliability: 0.9 },
    },
    {
      model_id: "gemma-12b",
      display_name: "Gemma 12B",
      provider_type: "lmstudio",
      endpoint_url: "http://localhost:1234",
      parameter_count: "12B",
      context_length: 8192,
      context_label: "8K",
      quantization: "Q4_K_M",
      size_gb: 7.2,
      capabilities: { json_mode: true, tools: true, vision: false, thinking: false },
      is_loaded: false,
      health_status: "unknown",
      measured: null,
    },
  ],
  total: 2,
  gpu: { name: "RTX 3080 Ti", vram_total_gb: 12.0, vram_available_gb: 3.5 },
};

const mockAssignments = {
  assignments: {
    gap_analysis: { model_id: "qwen3-4b", parameter_count: "4B", context_label: "262K", is_loaded: true, quantization: "Q4_K_M" },
    idea_generation: { model_id: "qwen3-4b", parameter_count: "4B", context_label: "262K", is_loaded: true, quantization: "Q4_K_M" },
  },
  total_stages: 2,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ModelStatusPanel", () => {
  it("renders model list with names", async () => {
    vi.mocked(getCatalog).mockResolvedValue(mockCatalog);
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    // Wait for data to load by waiting for model-dependent elements
    expect(await screen.findByText("Qwen3 4B")).toBeInTheDocument();
    expect(screen.getByText("Gemma 12B")).toBeInTheDocument();
  });

  it("shows loaded status indicator", async () => {
    vi.mocked(getCatalog).mockResolvedValue(mockCatalog);
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    await screen.findByTestId("model-qwen3-4b");
    // Loaded model has CheckCircle2 with aria-label="Loaded"
    expect(screen.getByLabelText("Loaded")).toBeInTheDocument();
  });

  it("shows not-loaded indicator for unloaded models", async () => {
    vi.mocked(getCatalog).mockResolvedValue(mockCatalog);
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    await screen.findByTestId("model-gemma-12b");
    expect(screen.getByLabelText("Not loaded")).toBeInTheDocument();
  });

  it("shows capability badges", async () => {
    vi.mocked(getCatalog).mockResolvedValue(mockCatalog);
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    await screen.findByTestId("model-qwen3-4b");
    expect(screen.getAllByText("JSON").length).toBeGreaterThan(0);
    expect(screen.getByText("Think")).toBeInTheDocument();
  });

  it("shows GPU info when available", async () => {
    vi.mocked(getCatalog).mockResolvedValue(mockCatalog);
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    expect(await screen.findByText(/RTX 3080 Ti/)).toBeInTheDocument();
    expect(screen.getByText(/3\.5 \/ 12\.0 GB free/)).toBeInTheDocument();
  });

  it("shows stage routing assignments", async () => {
    vi.mocked(getCatalog).mockResolvedValue(mockCatalog);
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    expect(await screen.findByTestId("stage-assignments")).toBeInTheDocument();
    expect(screen.getByText(/Stage Routing/)).toBeInTheDocument();
    expect(screen.getByText(/gap analysis: qwen3-4b/)).toBeInTheDocument();
  });

  it("shows error when catalog fails", async () => {
    vi.mocked(getCatalog).mockRejectedValue(new Error("Connection refused"));
    vi.mocked(getAssignments).mockResolvedValue(mockAssignments);

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    expect(await screen.findByText("Failed to load model status")).toBeInTheDocument();
  });

  it("shows no-models message when catalog is empty", async () => {
    vi.mocked(getCatalog).mockResolvedValue({ models: [], total: 0, gpu: null });
    vi.mocked(getAssignments).mockResolvedValue({ assignments: {}, total_stages: 0 });

    render(<ModelStatusPanel />, { wrapper: createWrapper() });

    expect(await screen.findByTestId("no-models")).toBeInTheDocument();
  });
});
