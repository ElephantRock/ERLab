import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GovernancePanel } from "@/components/ideas/governance-panel";
import type { TimelineResponse } from "@/api/governance";

const mockGetTimeline = vi.fn();
const mockCreateDecision = vi.fn();

vi.mock("@/api/governance", () => ({
  getGovernanceTimeline: (...args: unknown[]) => mockGetTimeline(...args),
  createGovernanceDecision: (...args: unknown[]) => mockCreateDecision(...args),
}));

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const populatedTimeline: TimelineResponse = {
  events: [
    {
      type: "decision",
      timestamp: "2026-06-18T10:00:00Z",
      actor: "reviewer1",
      summary: "Approved",
      detail: { decision: "approved", note: "Great work" },
    },
    {
      type: "comment",
      timestamp: "2026-06-18T09:00:00Z",
      actor: "alice",
      summary: "Comment by alice",
      detail: { comment_id: 1, content_preview: "Needs more detail", parent_id: null },
    },
    {
      type: "section_revision",
      timestamp: "2026-06-18T08:00:00Z",
      actor: "user",
      summary: "Section 'abstract' section_refine",
      detail: { section_key: "abstract", source: "section_refine", trigger: "user", section_hash: "abc" },
    },
  ],
  total: 3,
};

describe("GovernancePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders title and decision buttons", () => {
    mockGetTimeline.mockReturnValue(new Promise(() => {}));
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    expect(screen.getByText("Governance")).toBeInTheDocument();
    expect(screen.getByTestId("gov-approve")).toBeInTheDocument();
    expect(screen.getByTestId("gov-needs-changes")).toBeInTheDocument();
    expect(screen.getByTestId("gov-deny")).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching timeline", () => {
    mockGetTimeline.mockReturnValue(new Promise(() => {}));
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders timeline events when populated", async () => {
    mockGetTimeline.mockResolvedValue(populatedTimeline);
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Great work/)).toBeInTheDocument();
    });

    expect(screen.getByText("Comment by alice")).toBeInTheDocument();
    expect(screen.getByText(/Section 'abstract'/)).toBeInTheDocument();
  });

  it("shows empty state when no timeline events", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], total: 0 });
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText("No governance activity yet.")).toBeInTheDocument();
    });
  });

  it("shows error on fetch failure", async () => {
    mockGetTimeline.mockRejectedValue(new Error("Network error"));
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Failed to load timeline")).toBeInTheDocument();
    });
  });

  it("shows latest decision badge in header", async () => {
    mockGetTimeline.mockResolvedValue(populatedTimeline);
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      // Badge says "Approved" — find by the badge class context
      const badges = screen.getAllByText("Approved");
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("calls createDecision on approve click", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], total: 0 });
    mockCreateDecision.mockResolvedValue({ id: 1 });
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("gov-approve")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("gov-approve"));

    await waitFor(() => {
      expect(mockCreateDecision).toHaveBeenCalledWith(7, "approved", undefined);
    });
  });

  it("sends note text with decision", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], total: 0 });
    mockCreateDecision.mockResolvedValue({ id: 1 });
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("gov-note-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("gov-note-input"), {
      target: { value: "Please fix methodology" },
    });
    fireEvent.click(screen.getByTestId("gov-needs-changes"));

    await waitFor(() => {
      expect(mockCreateDecision).toHaveBeenCalledWith(
        7,
        "needs_changes",
        "Please fix methodology",
      );
    });
  });

  it("disables buttons while mutation is pending", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], total: 0 });
    mockCreateDecision.mockReturnValue(new Promise(() => {})); // Never resolves
    render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("gov-approve")).not.toBeDisabled();
    });

    fireEvent.click(screen.getByTestId("gov-approve"));

    await waitFor(() => {
      expect(screen.getByTestId("gov-approve")).toBeDisabled();
      expect(screen.getByTestId("gov-deny")).toBeDisabled();
    });
  });

  it("clears note after successful decision", async () => {
    mockGetTimeline.mockResolvedValue({ events: [], total: 0 });
    mockCreateDecision.mockResolvedValue({ id: 1 });
    const { container } = render(<GovernancePanel ideaId={7} />, { wrapper: makeWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("gov-note-input")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("gov-note-input"), {
      target: { value: "Some note" },
    });
    fireEvent.click(screen.getByTestId("gov-approve"));

    await waitFor(() => {
      const textarea = screen.getByTestId("gov-note-input") as HTMLTextAreaElement;
      expect(textarea.value).toBe("");
    });
  });
});
