import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RevisionHistoryDrawer } from "@/components/ideas/revision-history-drawer";

vi.mock("@/api/ideas", () => ({
  getSectionRevisions: vi.fn(),
  restoreSection: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getSectionRevisions } from "@/api/ideas";
const mockedGetRevisions = vi.mocked(getSectionRevisions);

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const revisionWithReceipt = {
  revisions: [
    {
      id: 1,
      source: "section_refine",
      trigger: "user_manual",
      trigger_detail: null,
      section_hash: "abc123",
      model_receipt: {
        requested_model: "qwen/qwen3-4b-2507",
        served_model: "qwen/qwen3-4b-2507",
        provider: "openai",
        endpoint: "http://100.64.0.1:1234/v1",
        timestamp: "2026-06-18T10:25:06.506879+00:00",
        context_length: 32768,
      },
      quality_summary: {
        section: "evaluation_plan",
        passed: true,
        word_count: 350,
        min_words: 300,
        failures: [],
      },
      created_at: "2026-06-18T10:25:06Z",
      is_current: true,
    },
  ],
  synthetic_original: {
    source: "pipeline",
    section_hash: "prev_hash",
    quality_summary: {
      section: "evaluation_plan",
      passed: false,
      word_count: 282,
      min_words: 300,
      failures: ["word count 282 < 300"],
    },
    note: "Original pipeline output",
  },
  current_hash: "abc123",
};

const revisionModelMismatch = {
  revisions: [
    {
      id: 2,
      source: "section_refine",
      trigger: "user_manual",
      trigger_detail: null,
      section_hash: "def456",
      model_receipt: {
        requested_model: "gpt-4o",
        served_model: "gpt-4o-2024-08-06",
        provider: "openai",
        endpoint: "",
        timestamp: "2026-06-18T11:00:00Z",
        context_length: null,
      },
      quality_summary: null,
      created_at: "2026-06-18T11:00:00Z",
      is_current: true,
    },
  ],
  synthetic_original: null,
  current_hash: "def456",
};

describe("RevisionHistoryDrawer — Receipt Visibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders receipt badge with served model", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByTestId("receipt-badge")).toBeInTheDocument();
    });

    expect(screen.getByText("qwen/qwen3-4b-2507")).toBeInTheDocument();
  });

  it("shows provider in receipt badge", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/openai/)).toBeInTheDocument();
    });
  });

  it("shows context length when available", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText("32,768 tokens")).toBeInTheDocument();
    });
  });

  it("shows timestamp in receipt badge", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByTestId("receipt-badge")).toBeInTheDocument();
    });

    // Timestamp is rendered via toLocaleString()
    const receipt = screen.getByTestId("receipt-badge");
    expect(receipt.textContent).toContain("2026");
  });

  it("shows verifiable label", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText(/Verifiable/)).toBeInTheDocument();
    });
  });

  it("shows both requested and served model when they differ", async () => {
    mockedGetRevisions.mockResolvedValue(revisionModelMismatch);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="def456"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText("gpt-4o-2024-08-06")).toBeInTheDocument();
    });
    // Should also show requested model since they differ
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("does NOT show receipt badge on pipeline original entry", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByTestId("revision-synthetic-original")).toBeInTheDocument();
    });

    // Synthetic original should NOT have a receipt badge
    const original = screen.getByTestId("revision-synthetic-original");
    expect(original.querySelector("[data-testid='receipt-badge']")).toBeNull();
  });

  it("shows endpoint when present", async () => {
    mockedGetRevisions.mockResolvedValue(revisionWithReceipt);
    render(
      <RevisionHistoryDrawer
        ideaId={10}
        sectionKey="evaluation_plan"
        sectionLabel="Evaluation Plan"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    await waitFor(() => {
      expect(screen.getByText("http://100.64.0.1:1234/v1")).toBeInTheDocument();
    });
  });
});
