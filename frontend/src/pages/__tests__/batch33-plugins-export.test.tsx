import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";

// ── Mock API ─────────────────────────────────────────────────────
vi.mock("@/api/exports", () => ({
  listPlugins: vi.fn(),
  installPlugin: vi.fn(),
  exportPdf: vi.fn(),
  bulkExport: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { ExportDialog } from "@/components/export/export-dialog";
import PluginsPage from "@/pages/plugins";
import { listPlugins, installPlugin, exportPdf } from "@/api/exports";

const mockedListPlugins = vi.mocked(listPlugins);
const mockedInstallPlugin = vi.mocked(installPlugin);
const mockedExportPdf = vi.mocked(exportPdf);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── TEST-33-02-01: Export dialog shows format options ─────────────

describe("ExportDialog", () => {
  it("TEST-33-02-01: shows format options when opened", async () => {
    renderWithProviders(<ExportDialog ideaId={1} />);

    // Click the trigger to open
    const trigger = screen.getByTestId("export-dialog-trigger");
    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByTestId("export-dialog")).toBeInTheDocument();
    });

    // Should show format select and submit button
    expect(screen.getByTestId("export-format-select")).toBeInTheDocument();
    expect(screen.getByTestId("export-submit-btn")).toBeInTheDocument();
  });

  // ── TEST-33-02-02: PDF export triggers download ──────────────────
  it("TEST-33-02-02: PDF export triggers download", async () => {
    const mockBlob = new Blob(["test pdf content"], { type: "application/pdf" });
    mockedExportPdf.mockResolvedValue(mockBlob);

    renderWithProviders(<ExportDialog ideaId={1} />);

    // Open the dialog
    const trigger = screen.getByTestId("export-dialog-trigger");
    fireEvent.click(trigger);

    await waitFor(() => {
      expect(screen.getByTestId("export-submit-btn")).toBeInTheDocument();
    });

    // Click export
    const btn = screen.getByTestId("export-submit-btn");
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockedExportPdf).toHaveBeenCalledWith({ idea_id: 1 });
    });
  });
});

// ── TEST-33-02-03: Plugins page lists available plugins ───────────

describe("PluginsPage", () => {
  it("TEST-33-02-03: lists available plugins", async () => {
    mockedListPlugins.mockResolvedValue({
      plugins: [
        { name: "pdf-export", version: "1.0.0", description: "Export ideas as PDF", enabled: true, metadata: {} },
        { name: "bulk-export", version: "1.0.0", description: "Bulk export as ZIP", enabled: true, metadata: {} },
        { name: "literature-search", version: "1.0.0", description: "Search literature", enabled: true, metadata: {} },
        { name: "knowledge-graph", version: "1.0.0", description: "Build knowledge graphs", enabled: true, metadata: {} },
      ],
      total: 4,
    });

    renderWithProviders(<PluginsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("plugin-list")).toBeInTheDocument();
    });

    expect(screen.getByTestId("plugin-card-pdf-export")).toBeInTheDocument();
    expect(screen.getByTestId("plugin-card-bulk-export")).toBeInTheDocument();
    expect(screen.getByTestId("plugin-card-literature-search")).toBeInTheDocument();
    expect(screen.getByTestId("plugin-card-knowledge-graph")).toBeInTheDocument();
  });

  // ── TEST-33-02-04: Install button installs plugin ────────────────
  it("TEST-33-02-04: install button installs plugin", async () => {
    mockedListPlugins.mockResolvedValue({ plugins: [], total: 0 });
    mockedInstallPlugin.mockResolvedValue({
      name: "test-plugin",
      version: "0.1.0",
      description: "A test plugin",
      enabled: true,
      metadata: {},
    });

    renderWithProviders(<PluginsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("plugin-install-card")).toBeInTheDocument();
    });

    const nameInput = screen.getByTestId("plugin-name-input");
    const descInput = screen.getByTestId("plugin-desc-input");
    const installBtn = screen.getByTestId("plugin-install-btn");

    fireEvent.change(nameInput, { target: { value: "test-plugin" } });
    fireEvent.change(descInput, { target: { value: "A test plugin" } });
    fireEvent.click(installBtn);

    await waitFor(() => {
      // mutationFn is called with (variables, mutationContext)
      const call = mockedInstallPlugin.mock.calls[0];
      expect(call[0]).toEqual({
        name: "test-plugin",
        description: "A test plugin",
      });
    });
  });
});
