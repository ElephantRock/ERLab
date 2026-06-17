/**
 * Tests for IdeaListItem component
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { IdeaListItem } from "@/components/ideas/idea-list-item";
import type { IdeaSummary } from "@/api/types";

const mockIdea: IdeaSummary = {
  id: 42,
  title: "Novel Transformer Architecture",
  domain: "NLP",
  novelty_score: 0.9,
  feasibility_score: 0.8,
  overall_score: 0.85,
  source_gap_ids: null,
  has_proposal: false,
  pipeline_run_id: 1,
  created_at: "2026-06-01T00:00:00Z",
};

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("IdeaListItem", () => {
  it("renders idea title and domain", () => {
    renderWithRouter(<IdeaListItem idea={mockIdea} />);
    expect(screen.getByText("Novel Transformer Architecture")).toBeInTheDocument();
    expect(screen.getByText("NLP")).toBeInTheDocument();
  });

  it("renders overall score as percentage", () => {
    renderWithRouter(<IdeaListItem idea={mockIdea} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("does not render score badge when score is null", () => {
    const noScore = { ...mockIdea, overall_score: null };
    renderWithRouter(<IdeaListItem idea={noScore} />);
    expect(screen.queryByText("85%")).not.toBeInTheDocument();
  });

  it("calls onClick when provided", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(<IdeaListItem idea={mockIdea} onClick={onClick} />);
    await user.click(screen.getByTestId("idea-list-item-42"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is keyboard accessible (role=button, tabIndex=0)", () => {
    renderWithRouter(<IdeaListItem idea={mockIdea} />);
    const item = screen.getByRole("button");
    expect(item).toHaveAttribute("tabindex", "0");
  });

  it("responds to Enter key", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(<IdeaListItem idea={mockIdea} onClick={onClick} />);
    const item = screen.getByTestId("idea-list-item-42");
    item.focus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledOnce();
  });
});
