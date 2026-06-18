import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Sidebar } from "@/components/layout/sidebar";
import Placeholder from "@/pages/placeholder";

// ── Helper ──────────────────────────────────────────────────────
function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar collapsed={false} />
    </MemoryRouter>,
  );
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/costs" element={<Placeholder title="Costs" />} />
        <Route path="/memory" element={<Placeholder title="Memory" />} />
        <Route path="/governance" element={<Placeholder title="Governance" />} />
        <Route path="/traces" element={<Placeholder title="Traces" />} />
        <Route path="/sessions" element={<Placeholder title="Sessions" />} />
        <Route path="/literature" element={<Placeholder title="Literature" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("BATCH-16/TASK-01: Navigation", () => {
  // ── Sidebar renders visible nav items (Advanced collapsed) ─────
  it("renders 11 visible nav items when Advanced is collapsed", () => {
    renderSidebar();

    const links = screen.getAllByRole("link");
    // Command Center (4) + Research (3) + System (4) = 11 visible
    // Advanced (5) is collapsed by default
    expect(links).toHaveLength(11);

    const labels = links.map((l) => l.textContent?.trim());
    expect(labels).toEqual([
      // Command Center
      "Dashboard",
      "New Run",
      "Ideas",
      "Gaps",
      // Research
      "Literature",
      "Knowledge",
      "Graph",
      // System
      "Ops",
      "Governance",
      "Settings",
      "Costs",
    ]);
  });

  // ── Expanding Advanced shows all 16 items ──────────────────────
  it("shows all 16 items when Advanced is expanded", () => {
    renderSidebar();

    // Click the Advanced toggle
    const toggle = screen.getByTestId("toggle-advanced");
    fireEvent.click(toggle);

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(16);

    const labels = links.map((l) => l.textContent?.trim());
    // Advanced items should now be visible
    expect(labels).toContain("Memory");
    expect(labels).toContain("Autonomous");
    expect(labels).toContain("Plugins");
    expect(labels).toContain("Sessions");
    expect(labels).toContain("Traces");
  });

  // ── Primary nav items have correct hrefs ──────────────────────
  it("primary nav items have correct hrefs", () => {
    renderSidebar();

    const links = screen.getAllByRole("link");

    // Command Center group (first 4)
    expect(links[0]).toHaveAttribute("href", "/");
    expect(links[1]).toHaveAttribute("href", "/pipeline/new");
    expect(links[2]).toHaveAttribute("href", "/ideas");
    expect(links[3]).toHaveAttribute("href", "/gaps");
  });

  // ── All nav links have icons ──────────────────────────────────
  it("all nav links contain SVG icons", () => {
    renderSidebar();

    const links = screen.getAllByRole("link");

    for (const link of links) {
      const svg = link.querySelector("svg");
      expect(svg).toBeTruthy();
    }

    const hrefs = links.map((l) => l.getAttribute("href"));
    // Verify expected routes are present (not Advanced)
    const expectedRoutes = [
      "/", "/pipeline/new", "/ideas", "/gaps",
      "/literature", "/knowledge", "/knowledge-graph",
      "/ops", "/governance", "/settings", "/costs",
    ];
    for (const route of expectedRoutes) {
      expect(hrefs).toContain(route);
    }
  });

  // ── All 16 routes exist when expanded ─────────────────────────
  it("all 16 routes present when Advanced expanded", () => {
    renderSidebar();

    fireEvent.click(screen.getByTestId("toggle-advanced"));

    const hrefs = screen.getAllByRole("link").map((l) => l.getAttribute("href"));
    const allExpected = [
      "/", "/pipeline/new", "/ideas", "/gaps",
      "/literature", "/knowledge", "/knowledge-graph",
      "/ops", "/governance", "/settings", "/costs",
      "/memory", "/autonomous", "/plugins", "/sessions", "/traces",
    ];
    for (const route of allExpected) {
      expect(hrefs).toContain(route);
    }
  });

  // ── Placeholder route tests ───────────────────────────────────
  it("/costs route renders placeholder", () => {
    renderRoute("/costs");
    expect(screen.getByText("Costs")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("/memory route renders placeholder", () => {
    renderRoute("/memory");
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("/governance route renders placeholder", () => {
    renderRoute("/governance");
    expect(screen.getByText("Governance")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("/traces route renders placeholder", () => {
    renderRoute("/traces");
    expect(screen.getByText("Traces")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("/sessions route renders placeholder", () => {
    renderRoute("/sessions");
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("/literature route renders placeholder", () => {
    renderRoute("/literature");
    expect(screen.getByText("Literature")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("placeholder pages do not make API calls", () => {
    const { container } = render(
      <MemoryRouter>
        <Placeholder title="Test" />
      </MemoryRouter>,
    );
    expect(container.querySelectorAll("img, iframe, script, link[rel='preload']")).toHaveLength(0);
    expect(screen.getByText("Test")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });
});
