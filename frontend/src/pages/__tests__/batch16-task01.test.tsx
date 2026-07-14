/**
 * Navigation tests — Loop-Based IA (Phase 1 rebuild).
 *
 * Replaces the old Studio Layout tests. The new IA is organized by
 * PRODUCT.md's Core Loop: DIRECT/TRIAGE/READ/REFINE/GOVERN + SECONDARY.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Sidebar } from "@/components/layout/sidebar";
import Placeholder from "@/pages/placeholder";

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar collapsed={false} />
    </MemoryRouter>,
  );
}

describe("Navigation — Loop-Based IA", () => {
  it("renders Direct group items", () => {
    renderSidebar();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("New Run")).toBeInTheDocument();
    expect(screen.getByText("Autonomous")).toBeInTheDocument();
  });

  it("renders Triage group items", () => {
    renderSidebar();
    expect(screen.getByText("Results")).toBeInTheDocument();
    expect(screen.getByText("Gaps")).toBeInTheDocument();
    expect(screen.getByText("Literature")).toBeInTheDocument();
  });

  it("renders Read group items (Knowledge Search — was orphaned)", () => {
    renderSidebar();
    expect(screen.getByText("Knowledge Search")).toBeInTheDocument();
  });

  it("renders Refine group items", () => {
    renderSidebar();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
  });

  it("renders Govern group items", () => {
    renderSidebar();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("renders Secondary group items (below separator)", () => {
    renderSidebar();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Costs")).toBeInTheDocument();
    expect(screen.getByText("Traces")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
  });

  it("Dashboard links to /", () => {
    renderSidebar();
    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).toHaveAttribute("href", "/");
  });

  it("Results links to /ideas", () => {
    renderSidebar();
    const resultsLink = screen.getByText("Results").closest("a");
    expect(resultsLink).toHaveAttribute("href", "/ideas");
  });

  it("Review links to /governance", () => {
    renderSidebar();
    const reviewLink = screen.getByText("Review").closest("a");
    expect(reviewLink).toHaveAttribute("href", "/governance");
  });

  it("Knowledge Search links to /knowledge (was orphaned)", () => {
    renderSidebar();
    const ksLink = screen.getByText("Knowledge Search").closest("a");
    expect(ksLink).toHaveAttribute("href", "/knowledge");
  });

  // Placeholder route tests
  it("/costs route renders placeholder", () => {
    render(
      <MemoryRouter initialEntries={["/costs"]}>
        <Routes><Route path="/costs" element={<Placeholder title="Costs" />} /></Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Costs")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });

  it("/literature route renders placeholder", () => {
    render(
      <MemoryRouter initialEntries={["/literature"]}>
        <Routes><Route path="/literature" element={<Placeholder title="Literature" />} /></Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Literature")).toBeInTheDocument();
    expect(screen.getByText("This page is coming soon.")).toBeInTheDocument();
  });
});
