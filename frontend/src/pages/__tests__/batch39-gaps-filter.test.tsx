import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import GapsExplorer from "@/pages/gaps-explorer";
import type { ResearchGap, GapListResponse } from "@/api/types";

// ── JSDOM polyfills for Radix UI ─────────────────────────────────
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

// Radix UI Select calls scrollIntoView on highlighted items
Element.prototype.scrollIntoView = vi.fn();

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ── Mock API ─────────────────────────────────────────────────────
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
  idea_count: 2,
};

const populatedResponse: GapListResponse = {
  gaps: [sampleGap],
  total: 1,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("GapsExplorer — BATCH-39 Search/Filter/Sort", () => {
  // ── TEST-39-02-01: Search input renders and updates on type ─────
  it("TEST-39-02-01: search input renders and updates on type", async () => {
    mockedListGaps.mockResolvedValue(populatedResponse);

    renderGapsExplorer();

    const searchInput = screen.getByLabelText("Search gaps by title or description");
    expect(searchInput).toBeInTheDocument();

    fireEvent.change(searchInput, { target: { value: "transfer" } });
    expect(searchInput).toHaveValue("transfer");

    await waitFor(() => {
      expect(mockedListGaps).toHaveBeenCalledWith(
        expect.objectContaining({ search: "transfer" }),
      );
    });
  });

  // ── TEST-39-02-02: Gap type filter renders with 4 options ──────
  it("TEST-39-02-02: gap type filter renders with options", async () => {
    mockedListGaps.mockResolvedValue(populatedResponse);

    renderGapsExplorer();

    // The trigger button should exist
    const trigger = screen.getByLabelText("Filter by gap type");
    expect(trigger).toBeInTheDocument();

    // Open the dropdown
    await act(async () => {
      fireEvent.click(trigger);
    });

    // Check that the 4 gap type options render in the portal
    await waitFor(() => {
      expect(screen.getByText("Methodological")).toBeInTheDocument();
      expect(screen.getByText("Empirical")).toBeInTheDocument();
      expect(screen.getByText("Theoretical")).toBeInTheDocument();
      expect(screen.getByText("Cross-domain")).toBeInTheDocument();
    });
  });

  // ── TEST-39-02-03: Confidence slider renders with label ────────
  it("TEST-39-02-03: confidence slider renders with label", async () => {
    mockedListGaps.mockResolvedValue(populatedResponse);

    renderGapsExplorer();

    const label = screen.getByText(/Min Confidence: 0\.0/);
    expect(label).toBeInTheDocument();

    const slider = screen.getByLabelText("Minimum confidence filter");
    expect(slider).toBeInTheDocument();
  });

  // ── TEST-39-02-04: Sort dropdown renders with confidence/date/type options ──
  it("TEST-39-02-04: sort dropdown renders with correct options", async () => {
    mockedListGaps.mockResolvedValue(populatedResponse);

    renderGapsExplorer();

    const trigger = screen.getByLabelText("Sort gaps by");
    expect(trigger).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(trigger);
    });

    await waitFor(() => {
      expect(screen.getAllByText("Confidence").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Date")).toBeInTheDocument();
      expect(screen.getByText("Type")).toBeInTheDocument();
    });
  });

  // ── TEST-39-02-05: Filters passed as query params to API ───────
  it("TEST-39-02-05: filters are passed as query params to API", async () => {
    mockedListGaps.mockResolvedValue(populatedResponse);

    renderGapsExplorer();

    // Verify initial call has default params
    await waitFor(() => {
      expect(mockedListGaps).toHaveBeenCalledWith(
        expect.objectContaining({
          sort_by: "confidence",
          sort_order: "desc",
        }),
      );
    });

    // Type in search
    const searchInput = screen.getByLabelText("Search gaps by title or description");
    fireEvent.change(searchInput, { target: { value: "test" } });

    await waitFor(() => {
      expect(mockedListGaps).toHaveBeenCalledWith(
        expect.objectContaining({ search: "test" }),
      );
    });
  });

  // ── TEST-39-02-06: "N gaps found" displays total from API (HB-03) ──
  it("TEST-39-02-06: displays total count from API", async () => {
    const multiResponse: GapListResponse = {
      gaps: [
        sampleGap,
        { ...sampleGap, id: 2, title: "Second gap", confidence: 0.5 },
      ],
      total: 42,
    };
    mockedListGaps.mockResolvedValue(multiResponse);

    renderGapsExplorer();

    await waitFor(() => {
      expect(screen.getByText("42 gaps found")).toBeInTheDocument();
    });
  });
});
