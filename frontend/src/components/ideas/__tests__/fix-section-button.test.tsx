import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FixSectionButton } from "@/components/ideas/fix-section-button";

const mockRefineSection = vi.fn();
vi.mock("@/api/ideas", () => ({
  refineSection: (...args: unknown[]) => mockRefineSection(...args),
}));

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("FixSectionButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Fix Section button initially", () => {
    render(
      <FixSectionButton
        ideaId={1}
        sectionKey="related_work"
        sectionLabel="Related Work"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    expect(screen.getByTestId("fix-button-related_work")).toBeInTheDocument();
    expect(screen.getByText("Fix Section")).toBeInTheDocument();
  });

  it("shows confirmation when clicked", () => {
    render(
      <FixSectionButton
        ideaId={1}
        sectionKey="related_work"
        sectionLabel="Related Work"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    fireEvent.click(screen.getByTestId("fix-button-related_work"));

    expect(screen.getByTestId("fix-confirm-related_work")).toBeInTheDocument();
    expect(screen.getByText("Regenerate Related Work?")).toBeInTheDocument();
    expect(screen.getByText("Yes, regenerate")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("cancels back to button state", () => {
    render(
      <FixSectionButton
        ideaId={1}
        sectionKey="related_work"
        sectionLabel="Related Work"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    fireEvent.click(screen.getByTestId("fix-button-related_work"));
    fireEvent.click(screen.getByText("Cancel"));

    expect(screen.queryByTestId("fix-confirm-related_work")).not.toBeInTheDocument();
    expect(screen.getByTestId("fix-button-related_work")).toBeInTheDocument();
  });

  it("calls refineSection on confirm", async () => {
    mockRefineSection.mockResolvedValue({
      revision_id: 1,
      section_key: "related_work",
      previous_hash: "abc123",
      section_hash: "def456",
      quality_checks_before: [],
      quality_checks_after: [],
      model_receipt: { served_model: "gpt-4o", provider: "openai" },
    });

    render(
      <FixSectionButton
        ideaId={1}
        sectionKey="related_work"
        sectionLabel="Related Work"
        currentHash="abc123"
        failureHints={["word count 45 < 300"]}
      />,
      { wrapper: makeWrapper() },
    );

    fireEvent.click(screen.getByTestId("fix-button-related_work"));
    fireEvent.click(screen.getByTestId("fix-confirm-yes-related_work"));

    await waitFor(() => {
      expect(mockRefineSection).toHaveBeenCalledWith(
        1,
        "related_work",
        "abc123",
        { failure_hints: ["word count 45 < 300"] },
      );
    });
  });

  it("shows loading state during regeneration", async () => {
    mockRefineSection.mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    render(
      <FixSectionButton
        ideaId={1}
        sectionKey="related_work"
        sectionLabel="Related Work"
        currentHash="abc123"
      />,
      { wrapper: makeWrapper() },
    );

    fireEvent.click(screen.getByTestId("fix-button-related_work"));
    fireEvent.click(screen.getByTestId("fix-confirm-yes-related_work"));

    await waitFor(() => {
      expect(screen.getByText("Regenerating...")).toBeInTheDocument();
    });
  });
});
