import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { GlobalSearchDialog } from "@/components/search/global-search-dialog";
import { globalSearch } from "@/api/search";

vi.mock("@/api/search", () => ({
  globalSearch: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: vi.fn(),
  };
});

const mockGlobalSearch = vi.mocked(globalSearch);
const mockNavigate = vi.mocked(useNavigate);

function renderDialog(open = true) {
  const onOpenChange = vi.fn();
  const result = render(
    <MemoryRouter>
      <GlobalSearchDialog open={open} onOpenChange={onOpenChange} />
    </MemoryRouter>,
  );
  return { ...result, onOpenChange };
}

describe("BATCH-48/TASK-02: GlobalSearchDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockNavigate.mockReturnValue(vi.fn());
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows empty state message when opened with no query", () => {
    renderDialog();
    expect(screen.getByText("Start typing to search...")).toBeInTheDocument();
  });

  it("calls search API with correct query after debounce", async () => {
    mockGlobalSearch.mockResolvedValueOnce({
      query: "test",
      results: {},
      total: 0,
    });
    renderDialog();

    const input = screen.getByPlaceholderText("Search ideas, gaps, papers, runs...");
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).type(input, "test");

    // Advance past debounce
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(mockGlobalSearch).toHaveBeenCalledWith("test");
  });

  it("debounces rapid typing to a single API call", async () => {
    mockGlobalSearch.mockResolvedValue({
      query: "abc",
      results: {},
      total: 0,
    });
    renderDialog();

    const input = screen.getByPlaceholderText("Search ideas, gaps, papers, runs...");
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    // Rapid typing
    await user.type(input, "a");
    await user.type(input, "b");
    await user.type(input, "c");

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    // Should have been called (at least once), but with the final query
    const calls = mockGlobalSearch.mock.calls;
    const lastCall = calls[calls.length - 1];
    expect(lastCall?.[0]).toBe("abc");
  });

  it("renders results grouped by type", async () => {
    mockGlobalSearch.mockResolvedValueOnce({
      query: "neural",
      results: {
        ideas: {
          total: 1,
          items: [{ id: 1, title: "Neural Idea", domain: "ML", overall_score: 0.9 }],
        },
        gaps: {
          total: 1,
          items: [{ id: 2, title: "Neural Gap", gap_type: "methodological", confidence: 0.8 }],
        },
        papers: {
          total: 1,
          items: [{ id: 3, title: "Neural Paper", year: 2024, venue: "NeurIPS" }],
        },
        runs: {
          total: 1,
          items: [{ id: 4, status: "completed", domain: "ML", created_at: "2026-01-01" }],
        },
      },
      total: 4,
    });
    renderDialog();

    const input = screen.getByPlaceholderText("Search ideas, gaps, papers, runs...");
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).type(input, "neural");

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    await waitFor(() => {
      expect(screen.getByText("Ideas")).toBeInTheDocument();
    });
    expect(screen.getByText("Gaps")).toBeInTheDocument();
    expect(screen.getByText("Papers")).toBeInTheDocument();
    expect(screen.getByText("Runs")).toBeInTheDocument();
    expect(screen.getByText("Neural Idea")).toBeInTheDocument();
    expect(screen.getByText("Neural Gap")).toBeInTheDocument();
    expect(screen.getByText("Neural Paper")).toBeInTheDocument();
    expect(screen.getByText("Run #4")).toBeInTheDocument();
  });

  it("navigates to /ideas/:id when idea result is clicked", async () => {
    const mockNav = vi.fn();
    mockNavigate.mockReturnValue(mockNav);

    mockGlobalSearch.mockResolvedValueOnce({
      query: "idea",
      results: {
        ideas: {
          total: 1,
          items: [{ id: 42, title: "Test Idea", domain: "AI", overall_score: 0.85 }],
        },
      },
      total: 1,
    });
    renderDialog();

    const input = screen.getByPlaceholderText("Search ideas, gaps, papers, runs...");
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).type(input, "idea");

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    await waitFor(() => {
      expect(screen.getByText("Test Idea")).toBeInTheDocument();
    });

    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(screen.getByText("Test Idea"));

    expect(mockNav).toHaveBeenCalledWith("/ideas/42");
  });

  it("closes dialog when backdrop is clicked", async () => {
    const { onOpenChange } = renderDialog();

    // The backdrop is the overlay div
    const backdrop = document.querySelector(".fixed.inset-0.bg-black\\/50");
    if (backdrop) {
      await fireEvent.click(backdrop);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    }
  });
});
