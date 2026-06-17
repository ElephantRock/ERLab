/**
 * Tests for shared state components: ErrorCard, LoadingGrid, EmptyState
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorCard } from "@/components/ui/error-card";
import { LoadingGrid } from "@/components/ui/loading-grid";
import { EmptyState } from "@/components/ui/empty-state";
import { Lightbulb, AlertCircle } from "lucide-react";

// ── ErrorCard ────────────────────────────────────────────────────

describe("ErrorCard", () => {
  it("renders the message", () => {
    render(<ErrorCard message="Failed to load data" />);
    expect(screen.getByText("Failed to load data")).toBeInTheDocument();
  });

  it("renders error detail when provided", () => {
    render(<ErrorCard message="Error loading" error="Network timeout" />);
    expect(screen.getByText("Error loading")).toBeInTheDocument();
    expect(screen.getByText("Network timeout")).toBeInTheDocument();
  });

  it("does not render error detail when absent", () => {
    render(<ErrorCard message="Something went wrong" />);
    expect(screen.queryByText("Network timeout")).not.toBeInTheDocument();
  });

  it("has role=alert for accessibility", () => {
    render(<ErrorCard message="Error" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("uses default data-testid", () => {
    render(<ErrorCard message="Error" />);
    expect(screen.getByTestId("error-card")).toBeInTheDocument();
  });

  it("accepts custom data-testid", () => {
    render(<ErrorCard message="Error" testId="custom-error" />);
    expect(screen.getByTestId("custom-error")).toBeInTheDocument();
  });
});

// ── LoadingGrid ──────────────────────────────────────────────────

describe("LoadingGrid", () => {
  it("renders default 3 skeleton rows", () => {
    const { container } = render(<LoadingGrid />);
    const skeletons = container.querySelectorAll("[data-slot]");
    // Skeleton renders a div; just verify 3 children in the grid
    const grid = screen.getByTestId("loading-grid");
    expect(grid.children).toHaveLength(3);
  });

  it("renders custom count of rows", () => {
    render(<LoadingGrid count={5} />);
    const grid = screen.getByTestId("loading-grid");
    expect(grid.children).toHaveLength(5);
  });

  it("has role=status for accessibility", () => {
    render(<LoadingGrid />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("accepts custom data-testid", () => {
    render(<LoadingGrid testId="custom-loading" />);
    expect(screen.getByTestId("custom-loading")).toBeInTheDocument();
  });
});

// ── EmptyState ───────────────────────────────────────────────────

describe("EmptyState", () => {
  it("renders icon and title", () => {
    render(<EmptyState icon={Lightbulb} title="No ideas yet" />);
    expect(screen.getByText("No ideas yet")).toBeInTheDocument();
  });

  it("renders message when provided", () => {
    render(
      <EmptyState
        icon={Lightbulb}
        title="No ideas"
        message="Start a pipeline to generate ideas."
      />,
    );
    expect(screen.getByText("No ideas")).toBeInTheDocument();
    expect(screen.getByText("Start a pipeline to generate ideas.")).toBeInTheDocument();
  });

  it("renders action button when provided", () => {
    render(
      <EmptyState
        icon={AlertCircle}
        title="No data"
        action={<button>Click me</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  it("does not render action when absent", () => {
    render(<EmptyState icon={Lightbulb} title="Empty" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("uses default data-testid", () => {
    render(<EmptyState icon={Lightbulb} title="Empty" />);
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });
});
