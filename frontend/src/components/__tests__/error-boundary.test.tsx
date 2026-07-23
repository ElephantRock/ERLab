/**
 * F1.6.2 root + route boundary tests.
 *
 * Verifies:
 *   - root boundary renders full-screen fallback, event_id visible
 *   - route boundary renders INSIDE AppShell (sidebar/header preserved)
 *   - route boundary Retry clears state without reload
 *   - route boundary Dashboard navigates
 *   - location.key change resets the boundary (same-path query transition)
 *   - route transition to a healthy route clears boundary state
 *   - persistent failure does not infinite-loop
 *   - lazy_route_error shows Reload and retry (with marker semantics)
 *   - event_id is rendered synchronously (no async wait)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, Link } from "react-router-dom";
import React from "react";

vi.mock("@/api/clients/diagnostics-client", () => ({
  sendRuntimeErrorReport: vi.fn().mockResolvedValue({ status: "accepted", event_id: "evt-test" }),
}));

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { RootErrorBoundary } from "@/components/error-boundary";
import { RouteErrorBoundary } from "@/components/route-error-boundary";
import { LazyRouteError } from "@/lib/lazy-route";
import { _clearAllForTesting as clearLazyRetry } from "@/lib/lazy-route-retry";
import { _resetForTesting as resetIncidentRegistry } from "@/lib/runtime-error-registry";
import { _forceUninstallForTesting as forceUninstallObservers } from "@/lib/runtime-observers";

beforeEach(() => {
  vi.clearAllMocks();
  resetIncidentRegistry();
  clearLazyRetry();
  forceUninstallObservers();
});

afterEach(() => {
  forceUninstallObservers();
});

// ── Throw-on-demand component ─────────────────────────────────────────

function BoomFactory({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("kaboom from BoomFactory");
  return <div data-testid="healthy-content">Healthy content</div>;
}

// ── Root boundary ─────────────────────────────────────────────────────

describe("RootErrorBoundary (F1.6.2)", () => {
  it("renders full-screen fallback with event_id when descendant throws", () => {
    render(
      <RootErrorBoundary>
        <BoomFactory shouldThrow={true} />
      </RootErrorBoundary>,
    );
    expect(screen.getByTestId("root-error-fallback")).toBeInTheDocument();
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    // event_id is rendered synchronously.
    expect(screen.getByTestId("root-error-event-id")).toBeInTheDocument();
    expect(screen.getByTestId("root-error-event-id").textContent).toMatch(/^Reference: evt-/);
  });

  it("Retry clears boundary state (renders children again)", () => {
    // The boundary's retry clears hasError; the children (which threw)
    // will throw again unless the underlying condition is repaired.
    // Use a mutable flag controlled from outside.
    const control = { shouldThrow: true };
    function ControlledChild() {
      if (control.shouldThrow) throw new Error("controlled");
      return <div data-testid="recovered">Recovered</div>;
    }
    render(
      <RootErrorBoundary>
        <ControlledChild />
      </RootErrorBoundary>,
    );
    expect(screen.getByTestId("root-error-fallback")).toBeInTheDocument();
    // Repair the underlying condition, then retry.
    control.shouldThrow = false;
    fireEvent.click(screen.getByTestId("root-error-retry"));
    expect(screen.getByTestId("recovered")).toBeInTheDocument();
  });
});

// ── Route boundary ────────────────────────────────────────────────────

describe("RouteErrorBoundary (F1.6.2)", () => {
  // The route boundary renders fallback INSIDE its parent, so to prove
  // AppShell-preservation we mount it inside a frame that has a sidebar.

  function AppShellFrame({ children }: { children: React.ReactNode }) {
    return (
      <div>
        <nav data-testid="sidebar">Sidebar</nav>
        <main>{children}</main>
      </div>
    );
  }

  function Harness({ shouldThrow }: { shouldThrow: boolean }) {
    return (
      <MemoryRouter initialEntries={["/page"]}>
        <AppShellFrame>
          <RouteErrorBoundary>
            <BoomFactory shouldThrow={shouldThrow} />
          </RouteErrorBoundary>
        </AppShellFrame>
      </MemoryRouter>
    );
  }

  it("preserves AppShell (sidebar visible) when route throws", () => {
    render(<Harness shouldThrow={true} />);
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
  });

  it("renders event_id reference", () => {
    render(<Harness shouldThrow={true} />);
    expect(screen.getByTestId("route-error-event-id").textContent).toMatch(/^Reference: evt-/);
  });

  it("Retry clears boundary state (renders children again)", () => {
    const control = { shouldThrow: true };
    function ControlledChild() {
      if (control.shouldThrow) throw new Error("controlled");
      return <div data-testid="recovered">Recovered</div>;
    }
    render(
      <MemoryRouter initialEntries={["/page"]}>
        <AppShellFrame>
          <RouteErrorBoundary>
            <ControlledChild />
          </RouteErrorBoundary>
        </AppShellFrame>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
    control.shouldThrow = false;
    fireEvent.click(screen.getByTestId("route-error-retry"));
    expect(screen.getByTestId("recovered")).toBeInTheDocument();
  });

  it("Go to dashboard navigates to /", () => {
    function DashboardPage() {
      return <div data-testid="dashboard">Dashboard</div>;
    }
    function CrashingPage() {
      throw new Error("crash");
    }
    render(
      <MemoryRouter initialEntries={["/crash"]}>
        <AppShellFrame>
          <RouteErrorBoundary>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/crash" element={<CrashingPage />} />
            </Routes>
          </RouteErrorBoundary>
        </AppShellFrame>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("route-error-dashboard"));
    expect(screen.getByTestId("dashboard")).toBeInTheDocument();
  });

  it("location.key change resets the boundary (route transition)", () => {
    function PageA() {
      throw new Error("a crashes");
    }
    function PageB() {
      return <div data-testid="page-b">Page B healthy</div>;
    }
    // Place the navigation Link OUTSIDE the route boundary so it remains
    // clickable even when route A is showing its fallback.
    render(
      <MemoryRouter initialEntries={["/a"]}>
        <AppShellFrame>
          <nav>
            <Link to="/b" data-testid="nav-b">Go to B</Link>
          </nav>
          <RouteErrorBoundary>
            <Routes>
              <Route path="/a" element={<PageA />} />
              <Route path="/b" element={<PageB />} />
            </Routes>
          </RouteErrorBoundary>
        </AppShellFrame>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
    // Navigate to B — location.key changes, boundary remounts, B renders.
    fireEvent.click(screen.getByTestId("nav-b"));
    expect(screen.getByTestId("page-b")).toBeInTheDocument();
    // Fallback is gone.
    expect(screen.queryByTestId("route-error-fallback")).not.toBeInTheDocument();
  });

  it("persistent failure does not infinite-loop (one reset per location.key)", () => {
    function AlwaysBoom() {
      throw new Error("always");
    }
    render(
      <MemoryRouter initialEntries={["/page"]}>
        <AppShellFrame>
          <RouteErrorBoundary>
            <AlwaysBoom />
          </RouteErrorBoundary>
        </AppShellFrame>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
    // Clicking Retry re-renders AlwaysBoom which throws again — boundary
    // catches again. No loop (React's error boundary contract: max 1
    // catch per mount; retry creates a new mount which throws once).
    fireEvent.click(screen.getByTestId("route-error-retry"));
    // Fallback is still showing — no infinite loop, no crash.
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
  });
});

// ── Lazy-route failure ────────────────────────────────────────────────

describe("RouteErrorBoundary lazy-route failure (F1.6.3)", () => {
  function LazyFailureHarness() {
    return (
      <MemoryRouter initialEntries={["/lazy"]}>
        <RouteErrorBoundary>
          <LazyThrower />
        </RouteErrorBoundary>
      </MemoryRouter>
    );
  }

  function LazyThrower() {
    // Simulate what the route boundary sees when a lazy import failed:
    // throw LazyRouteError during render.
    throw new LazyRouteError();
  }

  beforeEach(() => {
    clearLazyRetry();
  });

  it("classifies LazyRouteError and shows Reload and retry when marker absent", () => {
    render(<LazyFailureHarness />);
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
    expect(screen.getByText(/This page failed to load/i)).toBeInTheDocument();
    expect(screen.getByTestId("route-error-reload")).toBeInTheDocument();
  });

  it("hides Reload when marker present (persistent fallback, no loop)", () => {
    // Pre-set the marker.
    window.sessionStorage.setItem(
      "erock_lazy_retry_" + (import.meta.env.VITE_BUILD_HASH ?? "dev") + "_/lazy",
      "1",
    );
    render(<LazyFailureHarness />);
    expect(screen.getByTestId("route-error-fallback")).toBeInTheDocument();
    expect(screen.getByText(/still couldn't load after a retry/i)).toBeInTheDocument();
    expect(screen.queryByTestId("route-error-reload")).not.toBeInTheDocument();
    expect(screen.getByTestId("route-error-dashboard")).toBeInTheDocument(); // still navigable
  });
});
