/**
 * Tests for DataView (INTERFACE_CONTRACT §2).
 *
 * Verifies the four-state composition:
 * - loading  → renders skeletons, role=status
 * - error    → renders ErrorCard + a "Try again" button wired to retry
 * - empty    → renders EmptyState (configured or generic)
 * - ready    → calls the children render-prop with the data
 *
 * And the structural guarantee: the four states never leak into the page
 * JSX. The page only ever sees `<DataView>` + a render-prop.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataView } from "@/components/ui/data-view";
import type { ResourceState } from "@/lib/useResource";
import { Lightbulb } from "lucide-react";

// ── loading ───────────────────────────────────────────────────────────

describe("DataView — loading", () => {
  it("renders skeletons with role=status", () => {
    const resource: ResourceState<string[]> = { status: "loading" };
    render(
      <DataView resource={resource}>
        {() => <div>never</div>}
      </DataView>,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByTestId("data-view-loading")).toBeInTheDocument();
  });

  it("respects loading.lines to control skeleton count", () => {
    const resource: ResourceState<string[]> = { status: "loading" };
    render(
      <DataView resource={resource} loading={{ lines: 5 }}>
        {() => <div />}
      </DataView>,
    );

    // The loading wrapper renders N skeletons plus one sr-only span.
    // Count only the skeletons (the animate-pulse divs).
    const wrapper = screen.getByTestId("data-view-loading");
    const skeletons = wrapper.querySelectorAll(".animate-pulse");
    expect(skeletons).toHaveLength(5);
  });

  it("announces loading to screen readers", () => {
    const resource: ResourceState<string[]> = { status: "loading" };
    render(
      <DataView resource={resource}>
        {() => <div />}
      </DataView>,
    );
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });
});

// ── error ─────────────────────────────────────────────────────────────

describe("DataView — error", () => {
  it("renders ErrorCard with the error message", () => {
    const resource: ResourceState<string[]> = {
      status: "error",
      error: new Error("Network down"),
      retry: () => {},
    };
    render(
      <DataView resource={resource}>
        {() => <div />}
      </DataView>,
    );

    expect(screen.getByTestId("data-view-error")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/Network down/)).toBeInTheDocument();
  });

  it("renders a Try again button wired to retry", () => {
    const retry = vi.fn();
    const resource: ResourceState<string[]> = {
      status: "error",
      error: new Error("fail"),
      retry,
    };
    render(
      <DataView resource={resource}>
        {() => <div />}
      </DataView>,
    );

    const button = screen.getByRole("button", { name: /Try again/i });
    fireEvent.click(button);
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("prefers error.onRetry over resource.retry when both are present", () => {
    const resourceRetry = vi.fn();
    const customRetry = vi.fn();
    const resource: ResourceState<string[]> = {
      status: "error",
      error: new Error("fail"),
      retry: resourceRetry,
    };
    render(
      <DataView resource={resource} error={{ onRetry: customRetry }}>
        {() => <div />}
      </DataView>,
    );

    fireEvent.click(screen.getByRole("button", { name: /Try again/i }));
    expect(customRetry).toHaveBeenCalledTimes(1);
    expect(resourceRetry).not.toHaveBeenCalled();
  });
});

// ── empty ─────────────────────────────────────────────────────────────

describe("DataView — empty", () => {
  it("renders the configured empty state", () => {
    const resource: ResourceState<string[]> = { status: "empty", data: [] };
    render(
      <DataView
        resource={resource}
        empty={{ what: "ideas", icon: Lightbulb, message: "Run a pipeline." }}
      >
        {() => <div>never</div>}
      </DataView>,
    );

    expect(screen.getByTestId("data-view-empty")).toBeInTheDocument();
    expect(screen.getByText(/No ideas yet/i)).toBeInTheDocument();
    expect(screen.getByText("Run a pipeline.")).toBeInTheDocument();
  });

  it("renders the configured title when provided", () => {
    const resource: ResourceState<string[]> = { status: "empty", data: [] };
    render(
      <DataView resource={resource} empty={{ title: "Custom empty title" }}>
        {() => <div />}
      </DataView>,
    );
    expect(screen.getByText("Custom empty title")).toBeInTheDocument();
  });

  it("renders a generic empty state when none is configured", () => {
    const resource: ResourceState<string[]> = { status: "empty", data: [] };
    render(
      <DataView resource={resource}>
        {() => <div />}
      </DataView>,
    );
    expect(screen.getByText(/Nothing here yet/i)).toBeInTheDocument();
  });

  it("renders the configured action when provided", () => {
    const resource: ResourceState<string[]> = { status: "empty", data: [] };
    render(
      <DataView
        resource={resource}
        empty={{ action: <button>Start a run</button> }}
      >
        {() => <div />}
      </DataView>,
    );
    expect(screen.getByRole("button", { name: "Start a run" })).toBeInTheDocument();
  });
});

// ── ready ─────────────────────────────────────────────────────────────

describe("DataView — ready", () => {
  it("calls the children render-prop with the data", () => {
    const resource: ResourceState<string[]> = {
      status: "ready",
      data: ["alpha", "beta"],
    };
    const renderProp = vi.fn((data: string[]) => (
      <ul>{data.map((d) => <li key={d}>{d}</li>)}</ul>
    ));

    render(<DataView resource={resource}>{renderProp}</DataView>);

    expect(screen.getByTestId("data-view-ready")).toBeInTheDocument();
    expect(renderProp).toHaveBeenCalledWith(["alpha", "beta"]);
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
  });

  it("does not render skeletons, error, or empty in the ready branch", () => {
    const resource: ResourceState<string[]> = {
      status: "ready",
      data: ["x"],
    };
    render(
      <DataView resource={resource}>
        {(d) => <div>{d.join(",")}</div>}
      </DataView>,
    );

    expect(screen.queryByTestId("data-view-loading")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-view-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-view-empty")).not.toBeInTheDocument();
  });
});

// ── exhaustiveness ────────────────────────────────────────────────────

describe("DataView — branch isolation", () => {
  it("ready branch never sees loading/error/empty DOM", () => {
    // Belt-and-braces: the discriminated union makes this a type guarantee,
    // but we verify the runtime rendering too.
    const resource: ResourceState<string[]> = {
      status: "ready",
      data: ["x"],
    };
    render(
      <DataView resource={resource}>{(d) => <div>{d[0]}</div>}</DataView>,
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
