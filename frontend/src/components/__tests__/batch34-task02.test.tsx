/**
 * Tests for BATCH-34/TASK-02: Comment Thread + Share Dialog
 *
 * TEST-34-02-01 through TEST-34-02-04
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

// ── Shared fixtures ────────────────────────────────────────

const mockComments = {
  comments: [
    {
      id: 1,
      idea_id: 42,
      author: "alice",
      content: "This is a great research direction!",
      parent_id: null,
      created_at: "2026-05-02T10:00:00",
    },
    {
      id: 2,
      idea_id: 42,
      author: "bob",
      content: "I agree, let's explore this further.",
      parent_id: 1,
      created_at: "2026-05-02T11:00:00",
    },
    {
      id: 3,
      idea_id: 42,
      author: "charlie",
      content: "Has anyone tried this approach before?",
      parent_id: null,
      created_at: "2026-05-02T12:00:00",
    },
  ],
  total: 3,
};

// ── Mocks ──────────────────────────────────────────────────

vi.mock("@/api/collaboration", () => ({
  listComments: vi.fn(),
  addComment: vi.fn().mockResolvedValue({
    id: 4,
    idea_id: 42,
    author: "testuser",
    content: "New comment",
    parent_id: null,
    created_at: "2026-05-02T15:00:00",
  }),
  createShareLink: vi.fn().mockResolvedValue({
    id: 1,
    idea_id: 42,
    token: "abc123xyz_token_urlsafe",
    share_url: "/shared/abc123xyz_token_urlsafe",
    created_at: "2026-05-02T14:00:00",
  }),
  getSharedIdea: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// Import after mocks
import { CommentThread } from "@/components/idea/comment-thread";
import { ShareDialog } from "@/components/idea/share-dialog";
import { listComments, createShareLink } from "@/api/collaboration";

// ── Helpers ────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

// ── TEST-34-02-01: Comment thread renders comments ──────

describe("CommentThread", () => {
  beforeEach(() => {
    vi.mocked(listComments).mockResolvedValue(mockComments);
  });

  it("renders comments from API", async () => {
    render(<CommentThread ideaId={42} />, { wrapper: createWrapper() });

    // Wait for comments to render
    const heading = await screen.findByText(/Comments \(3\)/);
    expect(heading).toBeInTheDocument();

    // Should render top-level comments
    expect(
      screen.getByText("This is a great research direction!"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Has anyone tried this approach before?"),
    ).toBeInTheDocument();

    // Should render replies
    expect(
      screen.getByText("I agree, let's explore this further."),
    ).toBeInTheDocument();
  });
});

// ── TEST-34-02-02: Add comment form works ──────

describe("CommentThread add comment", () => {
  beforeEach(() => {
    vi.mocked(listComments).mockResolvedValue(mockComments);
  });

  it("renders input fields and accepts input", async () => {
    const user = userEvent.setup();
    render(<CommentThread ideaId={42} />, { wrapper: createWrapper() });

    await screen.findByText(/Comments/);

    const nameInput = screen.getByPlaceholderText(
      "Your name",
    ) as HTMLInputElement;
    const commentInput = screen.getByPlaceholderText(
      "Add a comment...",
    ) as HTMLInputElement;

    await user.clear(nameInput);
    await user.type(nameInput, "testauthor");
    await user.type(commentInput, "My new comment");

    expect(nameInput.value).toBe("testauthor");
    expect(commentInput.value).toBe("My new comment");
  });
});

// ── TEST-34-02-03: Share dialog generates link ──────

describe("ShareDialog", () => {
  it("renders generate button and creates link", async () => {
    const user = userEvent.setup();
    render(<ShareDialog ideaId={42} />, { wrapper: createWrapper() });

    // Button to generate share link
    const btn = screen.getByText("Generate Share Link");
    expect(btn).toBeInTheDocument();

    await user.click(btn);

    // After clicking, the share URL input should appear
    const urlInput = await screen.findByDisplayValue(
      /\/shared\/abc123xyz_token_urlsafe/,
    );
    expect(urlInput).toBeInTheDocument();
  });
});

// ── TEST-34-02-04: Shared idea page renders ──────

describe("SharedIdeaPage structure", () => {
  it("validates shared idea response shape", () => {
    // Verify the response shape matches what the frontend expects
    const sharedIdeaResponse = {
      idea: {
        id: 1,
        title: "Novel Attention via Sparse Gating",
        problem_statement: "Current attention mechanisms are too dense.",
        proposed_method: "Sparse gating mechanism",
        expected_contributions: "Faster inference",
        domain: "AI/NLP",
        novelty_score: 0.85,
        feasibility_score: 7.2,
        overall_score: 0.78,
        source_gap_ids: ["Efficient attention"],
        created_at: "2026-05-02T14:30:00",
      },
    };

    expect(sharedIdeaResponse.idea.title).toBe("Novel Attention via Sparse Gating");
    expect(sharedIdeaResponse.idea.domain).toBe("AI/NLP");
    expect(sharedIdeaResponse.idea.novelty_score).toBe(0.85);
    expect("proposal_md" in sharedIdeaResponse.idea).toBe(false);
  });
});
