/**
 * Tests for StageModelEditor component.
 * Phase B: Editable Model Routing UI.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { StageModelEditor } from "@/components/settings/stage-model-editor";

// ── Mocks ───────────────────────────────────────────────────────

vi.mock("@/api/settings", () => ({
  getStages: vi.fn(),
  getCatalog: vi.fn(),
  getCertification: vi.fn(),
  getOverrides: vi.fn(),
  updateOverrides: vi.fn(),
  removeOverride: vi.fn(),
  clearAllOverrides: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

import {
  getStages,
  getCatalog,
  getCertification,
  getOverrides,
  updateOverrides,
  removeOverride,
  clearAllOverrides,
} from "@/api/settings";

const mockedGetStages = vi.mocked(getStages);
const mockedGetCatalog = vi.mocked(getCatalog);
const mockedGetCertification = vi.mocked(getCertification);
const mockedGetOverrides = vi.mocked(getOverrides);
const mockedUpdateOverrides = vi.mocked(updateOverrides);
const mockedRemoveOverride = vi.mocked(removeOverride);
const mockedClearAllOverrides = vi.mocked(clearAllOverrides);

// ── Fixtures ────────────────────────────────────────────────────

const sampleStages = {
  stages: [
    { name: "gap_analysis", label: "Gap Analysis", category: "thinking", needs_llm: true },
    { name: "idea_generation", label: "Idea Generation", category: "generation", needs_llm: true },
    { name: "ingestion", label: "Ingestion", category: "passthrough", needs_llm: false },
  ],
  total: 3,
};

const sampleCatalog = {
  models: [
    {
      model_id: "qwen/qwen3-4b-2507",
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
      measured: null,
    },
    {
      model_id: "llama-3.1-8b",
      display_name: "Llama 3.1 8B",
      provider_type: "lmstudio",
      endpoint_url: "http://localhost:1234",
      parameter_count: "8B",
      context_length: 131072,
      context_label: "131K",
      quantization: "Q5_K_M",
      size_gb: 5.8,
      capabilities: { json_mode: true, tools: true, vision: false, thinking: false },
      is_loaded: false,
      health_status: "healthy",
      measured: null,
    },
  ],
  total: 2,
  gpu: { name: "RTX 3080 Ti", vram_total_gb: 12, vram_available_gb: 6 },
};

const sampleCertification = {
  certifications: [
    {
      model_id: "qwen/qwen3-4b-2507",
      provider: "lmstudio",
      status: "approved_for_limited_use",
      allowed_stages: { idea_generation: "limited_use" },
    },
  ],
  total: 1,
};

// ── Helpers ─────────────────────────────────────────────────────

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderEditor() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <StageModelEditor />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function setupDefaultMocks() {
  mockedGetStages.mockResolvedValue(sampleStages);
  mockedGetCatalog.mockResolvedValue(sampleCatalog);
  mockedGetCertification.mockResolvedValue(sampleCertification);
  mockedGetOverrides.mockResolvedValue({ overrides: {}, total: 0 });
}

beforeEach(() => {
  vi.clearAllMocks();
  setupDefaultMocks();
});

// ── Tests ───────────────────────────────────────────────────────

describe("StageModelEditor", () => {
  it("renders stage rows for LLM stages only", async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("stage-row-gap_analysis")).toBeInTheDocument();
      expect(screen.getByTestId("stage-row-idea_generation")).toBeInTheDocument();
    });
    // Passthrough stage (needs_llm=false) should be hidden
    expect(screen.queryByTestId("stage-row-ingestion")).not.toBeInTheDocument();
  });

  it("shows auto-routing when no override exists", async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getAllByText("Auto (fitness-scored)").length).toBeGreaterThan(0);
    });
  });

  it("shows existing override when present", async () => {
    mockedGetOverrides.mockResolvedValue({
      overrides: { idea_generation: "qwen/qwen3-4b-2507" },
      total: 1,
    });
    renderEditor();
    await waitFor(() => {
      expect(screen.getByText("qwen/qwen3-4b-2507")).toBeInTheDocument();
    });
  });

  it("edit button opens dropdown selectors", async () => {
    const user = userEvent.setup();
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("edit-overrides")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("edit-overrides"));
    expect(screen.getByTestId("model-select-gap_analysis")).toBeInTheDocument();
    expect(screen.getByTestId("model-select-idea_generation")).toBeInTheDocument();
  });

  it("dropdown shows all models with certification indicators", async () => {
    const user = userEvent.setup();
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("edit-overrides")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("edit-overrides"));

    const select = screen.getByTestId("model-select-idea_generation") as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.text);

    // Qwen3 should show ✓ (certified for idea_generation)
    expect(options.some((t) => t.includes("Qwen3") && t.includes("✓"))).toBe(true);
    // Llama should show (uncertified)
    expect(options.some((t) => t.includes("Llama") && t.includes("uncertified"))).toBe(true);
  });

  it("shows warning when selecting uncertified model for stage", async () => {
    const user = userEvent.setup();
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("edit-overrides")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("edit-overrides"));

    // Select Qwen3 for gap_analysis (not certified for this stage)
    const select = screen.getByTestId("model-select-gap_analysis");
    await user.selectOptions(select, "qwen/qwen3-4b-2507");

    await waitFor(() => {
      expect(screen.getByTestId("warnings-panel")).toBeInTheDocument();
    });
  });

  it("save button calls updateOverrides with draft", async () => {
    const user = userEvent.setup();
    mockedUpdateOverrides.mockResolvedValue({
      overrides: { gap_analysis: "qwen/qwen3-4b-2507" },
      warnings: [],
      message: "Saved",
    });
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("edit-overrides")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("edit-overrides"));

    const select = screen.getByTestId("model-select-gap_analysis");
    await user.selectOptions(select, "qwen/qwen3-4b-2507");

    await user.click(screen.getByTestId("save-overrides"));

    await waitFor(() => {
      expect(mockedUpdateOverrides).toHaveBeenCalledWith(
        { gap_analysis: "qwen/qwen3-4b-2507" },
        false,
      );
    });
  });

  it("cancel button exits edit mode without saving", async () => {
    const user = userEvent.setup();
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("edit-overrides")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("edit-overrides"));
    await user.click(screen.getByTestId("cancel-edit"));

    expect(screen.queryByTestId("model-select-gap_analysis")).not.toBeInTheDocument();
  });

  it("reset all calls clearAllOverrides", async () => {
    const user = userEvent.setup();
    mockedGetOverrides.mockResolvedValue({
      overrides: { idea_generation: "qwen/qwen3-4b-2507" },
      total: 1,
    });
    mockedClearAllOverrides.mockResolvedValue({
      message: "Cleared",
      overrides: {},
    });
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("reset-all")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("reset-all"));

    await waitFor(() => {
      expect(mockedClearAllOverrides).toHaveBeenCalled();
    });
  });

  it("reset single stage calls removeOverride", async () => {
    const user = userEvent.setup();
    mockedGetOverrides.mockResolvedValue({
      overrides: { idea_generation: "qwen/qwen3-4b-2507" },
      total: 1,
    });
    mockedRemoveOverride.mockResolvedValue({
      message: "Removed",
      overrides: {},
    });
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId("reset-stage-idea_generation")).toBeInTheDocument();
    });
    await user.click(screen.getByTestId("reset-stage-idea_generation"));

    await waitFor(() => {
      expect(mockedRemoveOverride).toHaveBeenCalledWith("idea_generation");
    });
  });

  it("shows certified checkmark for certified assignment", async () => {
    mockedGetOverrides.mockResolvedValue({
      overrides: { idea_generation: "qwen/qwen3-4b-2507" },
      total: 1,
    });
    renderEditor();
    await waitFor(() => {
      const icon = screen.getByLabelText("Certified");
      expect(icon).toBeInTheDocument();
    });
  });

  it("shows warning icon for uncertified assignment", async () => {
    mockedGetOverrides.mockResolvedValue({
      overrides: { gap_analysis: "qwen/qwen3-4b-2507" },
      total: 1,
    });
    renderEditor();
    await waitFor(() => {
      const icon = screen.getByLabelText("Not certified");
      expect(icon).toBeInTheDocument();
    });
  });

  it("shows error card when no models available", async () => {
    mockedGetCatalog.mockResolvedValue({
      models: [],
      total: 0,
      gpu: null,
      error: "No providers configured",
    });
    renderEditor();
    await waitFor(() => {
      expect(screen.getByText(/No models available/i)).toBeInTheDocument();
    });
  });
});
