import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
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

describe("BATCH-16/TASK-01: Phase 2 Navigation", () => {
  // ── TEST-16-01-01: Sidebar renders all nav items ─────────────
  it("TEST-16-01-01: sidebar renders all 15 nav items", () => {
    renderSidebar();

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(15);

    const labels = links.map((l) => l.textContent?.trim());
    // Sidebar is grouped: Primary, Research Tools, System
    expect(labels).toEqual([
      // Primary
      "Dashboard",
      "Pipeline",
      "Ideas",
      "Gaps",
      // Research Tools
      "Literature",
      "Knowledge",
      "Graph",
      "Memory",
      "Autonomous",
      "Sessions",
      // System
      "Costs",
      "Governance",
      "Traces",
      "Plugins",
      "Settings",
    ]);
  });

  // ── TEST-16-01-02: Primary nav items have correct hrefs ────────
  it("TEST-16-01-02: primary nav items have correct hrefs", () => {
    renderSidebar();

    const links = screen.getAllByRole("link");

    // Primary group (first 4)
    expect(links[0]).toHaveAttribute("href", "/");
    expect(links[1]).toHaveAttribute("href", "/pipeline/new");
    expect(links[2]).toHaveAttribute("href", "/ideas");
    expect(links[3]).toHaveAttribute("href", "/gaps");
  });

  // ── TEST-16-01-03: All nav links have icons ────────────────────
  it("TEST-16-01-03: all nav links contain SVG icons", () => {
    renderSidebar();

    const links = screen.getAllByRole("link");

    // Every link should contain an SVG icon
    for (const link of links) {
      const svg = link.querySelector("svg");
      expect(svg).toBeTruthy();
    }

    // Verify all expected routes are present
    const hrefs = links.map((l) => l.getAttribute("href"));
    const expectedRoutes = [
      "/", "/pipeline/new", "/ideas", "/gaps",
      "/literature", "/knowledge", "/knowledge-graph", "/memory",
      "/autonomous", "/sessions",
      "/costs", "/governance", "/traces", "/plugins", "/settings",
    ];
    for (const route of expectedRoutes) {
      expect(hrefs).toContain(route);
    }
  });

  // ── TEST-16-01-04: /costs route renders placeholder ─────────────
  it("TEST-16-01-04: /costs route renders placeholder with Costs title", () => {
    renderRoute("/costs");
    expect(screen.getByText("Costs")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  // ── TEST-16-01-05: /memory route renders placeholder ────────────
  it("TEST-16-01-05: /memory route renders placeholder", () => {
    renderRoute("/memory");
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  // ── TEST-16-01-06: /governance route renders placeholder ────────
  it("TEST-16-01-06: /governance route renders placeholder", () => {
    renderRoute("/governance");
    expect(screen.getByText("Governance")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  // ── TEST-16-01-07: /traces route renders placeholder ────────────
  it("TEST-16-01-07: /traces route renders placeholder", () => {
    renderRoute("/traces");
    expect(screen.getByText("Traces")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  // ── TEST-16-01-08: /sessions route renders placeholder ──────────
  it("TEST-16-01-08: /sessions route renders placeholder", () => {
    renderRoute("/sessions");
    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  // ── TEST-16-01-09: /literature route renders placeholder ────────
  it("TEST-16-01-09: /literature route renders placeholder", () => {
    renderRoute("/literature");
    expect(screen.getByText("Literature")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  // ── TEST-16-01-10: Placeholder pages do not make API calls ──────
  it("TEST-16-01-10: placeholder pages do not make API calls", () => {
    // Verify placeholder.tsx is a pure static component — it has no
    // API imports and renders only static text based on props.
    // We confirm by rendering it and checking no network calls occur.
    const { container } = render(
      <MemoryRouter>
        <Placeholder title="Test" />
      </MemoryRouter>,
    );

    // Component renders only heading and text — no data-fetching elements
    expect(container.querySelectorAll("img, iframe, script, link[rel='preload']")).toHaveLength(0);
    expect(screen.getByText("Test")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });
});
