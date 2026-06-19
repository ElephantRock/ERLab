import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

describe("Navigation — Studio Layout", () => {
  it("renders Studio group items", () => {
    renderSidebar();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("New Run")).toBeInTheDocument();
    expect(screen.getByText("Results")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("renders Research group items", () => {
    renderSidebar();
    expect(screen.getByText("Gaps")).toBeInTheDocument();
    expect(screen.getByText("Literature")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Graph")).toBeInTheDocument();
  });

  it("renders System group items", () => {
    renderSidebar();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("Advanced is collapsed by default", () => {
    renderSidebar();
    expect(screen.queryByText("Costs")).not.toBeInTheDocument();
    expect(screen.queryByText("Traces")).not.toBeInTheDocument();
  });

  it("expands Advanced on click", () => {
    renderSidebar();
    fireEvent.click(screen.getByTestId("toggle-advanced"));
    expect(screen.getByText("Costs")).toBeInTheDocument();
    expect(screen.getByText("Traces")).toBeInTheDocument();
    expect(screen.getByText("Memory")).toBeInTheDocument();
  });

  it("Home links to /", () => {
    renderSidebar();
    const homeLink = screen.getByText("Home").closest("a");
    expect(homeLink).toHaveAttribute("href", "/");
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
