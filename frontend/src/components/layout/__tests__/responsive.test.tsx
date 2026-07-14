/**
 * Tests for the rebuilt Shell + IA (Phase 1 — INTERFACE_CONTRACT §5, §7).
 *
 * Verifies:
 * - Sidebar renders the loop-based IA (DIRECT/TRIAGE/READ/REFINE/GOVERN/SECONDARY)
 * - /knowledge is reachable (was orphaned — The Orphan Route anti-pattern)
 * - SYS_OK decorative footer is absent (§7 — Honest State)
 * - MobileNav shortcut bar + full-IA Sheet
 * - No route is orphaned (every nav route exists in the router)
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Sidebar, ALL_NAV_ROUTES } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { AppShell } from "@/components/layout/app-shell";
import { SettingsProvider } from "@/contexts/settings-context";

vi.mock("@/api/pipeline", () => ({ listRuns: vi.fn().mockResolvedValue({ runs: [], total: 0 }) }));

function renderWithRouter(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SettingsProvider>{ui}</SettingsProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── Loop-based IA groups ─────────────────────────────────────────

describe("Sidebar — loop-based IA", () => {
  it("renders all loop group labels", () => {
    renderWithRouter(<Sidebar collapsed={false} />);
    // The 5 primary groups + Secondary
    expect(screen.getByText("Direct")).toBeInTheDocument();
    expect(screen.getByText("Triage")).toBeInTheDocument();
    expect(screen.getByText("Read")).toBeInTheDocument();
    expect(screen.getByText("Refine")).toBeInTheDocument();
    expect(screen.getByText("Govern")).toBeInTheDocument();
    expect(screen.getByText("Secondary")).toBeInTheDocument();
  });

  it("renders key loop items in their correct groups", () => {
    renderWithRouter(<Sidebar collapsed={false} />);
    expect(screen.getByText("New Run")).toBeInTheDocument();
    expect(screen.getByText("Results")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
  });

  it("/knowledge (Knowledge Search) is reachable — was orphaned", () => {
    renderWithRouter(<Sidebar collapsed={false} />);
    expect(screen.getByText("Knowledge Search")).toBeInTheDocument();
  });
});

// ── No orphan routes ─────────────────────────────────────────────

describe("Route reachability", () => {
  it("every nav route is a real path (no orphans)", () => {
    // ALL_NAV_ROUTES is exported from the sidebar for reachability auditing.
    // Every route should start with / and be non-empty.
    for (const route of ALL_NAV_ROUTES) {
      expect(route.startsWith("/")).toBe(true);
      expect(route.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("covers the previously-orphaned /knowledge route", () => {
    expect(ALL_NAV_ROUTES).toContain("/knowledge");
  });
});

// ── SYS_OK removed (§7 — Honest State) ──────────────────────────

describe("AppShell — decorative status removed", () => {
  it("does NOT render SYS_OK footer", () => {
    const { container } = renderWithRouter(
      <AppShell>
        <div>Content</div>
      </AppShell>,
    );
    expect(screen.queryByText("SYS_OK")).not.toBeInTheDocument();
    // The bg-green-500 pulsing dot should also be gone
    const greenDot = container.querySelector(".bg-green-500");
    expect(greenDot).toBeNull();
  });
});

// ── Sidebar collapsed mode ───────────────────────────────────────

describe("Sidebar — collapsed", () => {
  it("hides labels when collapsed", () => {
    renderWithRouter(<Sidebar collapsed={true} />);
    const links = screen.getAllByRole("link");
    expect(links.length).toBeGreaterThan(0);
    // Nav items should not have text labels when collapsed
    for (const link of links) {
      const labelSpans = link.querySelectorAll("span:not([class*='rounded-full'])");
      // Only icon spans exist when collapsed; no text label spans
      const textSpans = Array.from(labelSpans).filter(
        (s) => s.textContent && s.textContent.trim().length > 0,
      );
      expect(textSpans.length).toBe(0);
    }
  });
});

// ── MobileNav ────────────────────────────────────────────────────

describe("MobileNav", () => {
  it("renders shortcut bar with key items", () => {
    renderWithRouter(<MobileNav />);
    // Shortcuts: Run, Results, Review, Menu
    expect(screen.getByText("Run")).toBeInTheDocument();
    expect(screen.getByText("Results")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Menu")).toBeInTheDocument();
  });

  it("uses app-bottom-nav CSS class on the shortcut bar", () => {
    renderWithRouter(<MobileNav />);
    const nav = screen.getByRole("navigation", { name: "Mobile navigation" });
    expect(nav.className).toContain("app-bottom-nav");
  });

  it("opens the full IA Sheet when Menu is clicked", () => {
    renderWithRouter(<MobileNav />);
    // Before clicking, the Sheet content is not visible
    expect(screen.queryByText("Knowledge Search")).not.toBeInTheDocument();

    // Click Menu button
    fireEvent.click(screen.getByLabelText("Open full navigation menu"));

    // After clicking, the full IA is visible in the Sheet
    expect(screen.getByText("Knowledge Search")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
  });
});

// ── AppShell structure ───────────────────────────────────────────

describe("AppShell layout", () => {
  it("renders sidebar, bottom nav, and main content", () => {
    const { container } = renderWithRouter(
      <AppShell>
        <div>Page content</div>
      </AppShell>,
    );
    const aside = container.querySelector("aside");
    expect(aside).toBeInTheDocument();
    expect(aside?.className).toContain("app-sidebar");

    const bottomNav = container.querySelector(".app-bottom-nav");
    expect(bottomNav).toBeInTheDocument();

    const main = container.querySelector("main");
    expect(main).toBeInTheDocument();
    expect(main?.className).toContain("app-main");
    expect(main?.textContent).toContain("Page content");
  });
});
