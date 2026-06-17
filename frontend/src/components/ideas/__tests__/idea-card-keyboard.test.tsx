/**
 * Phase 3: IdeaCard keyboard accessibility tests
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { IdeaCard } from "@/components/ideas/idea-card";
import type { IdeaSummary } from "@/api/types";

// Mock ScoreBadge to avoid pulling in complex deps
vi.mock("@/components/ideas/score-badge", () => ({
  ScoreBadge: ({ score }: { score: number }) => (
    <span data-testid="score-badge">{score}</span>
  ),
}));

const sampleIdea: IdeaSummary = {
  id: 42,
  title: "Keyboard Accessible Idea",
  domain: "HCI",
  novelty_score: 0.9,
  feasibility_score: 0.5,
  overall_score: 0.7,
  source_gap_ids: null,
  has_proposal: false,
  pipeline_run_id: 1,
  created_at: "2026-06-01T00:00:00Z",
};

describe("IdeaCard keyboard accessibility", () => {
  it("has role=button and tabIndex=0", () => {
    render(
      <MemoryRouter>
        <IdeaCard idea={sampleIdea} onClick={() => {}} />
      </MemoryRouter>
    );
    const card = screen.getByRole("button");
    expect(card).toHaveAttribute("tabindex", "0");
  });

  it("has aria-label with idea title", () => {
    render(
      <MemoryRouter>
        <IdeaCard idea={sampleIdea} onClick={() => {}} />
      </MemoryRouter>
    );
    expect(screen.getByLabelText("View idea: Keyboard Accessible Idea")).toBeInTheDocument();
  });

  it("fires onClick on Enter key", () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <IdeaCard idea={sampleIdea} onClick={onClick} />
      </MemoryRouter>
    );
    const card = screen.getByRole("button");
    fireEvent.keyDown(card, { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("fires onClick on Space key", () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <IdeaCard idea={sampleIdea} onClick={onClick} />
      </MemoryRouter>
    );
    const card = screen.getByRole("button");
    fireEvent.keyDown(card, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("does not fire onClick on other keys", () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <IdeaCard idea={sampleIdea} onClick={onClick} />
      </MemoryRouter>
    );
    const card = screen.getByRole("button");
    fireEvent.keyDown(card, { key: "Tab" });
    expect(onClick).not.toHaveBeenCalled();
  });
});
