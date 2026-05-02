import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PaperCard } from "@/components/literature/paper-card";
import type { Paper } from "@/api/literature";

const samplePaper: Paper = {
  id: "ss-abc123",
  source: "semantic_scholar",
  title: "Attention Is All You Need",
  abstract: "We propose a new network architecture, the Transformer.",
  authors: [{ name: "Ashish Vaswani" }, { name: "Noam Shazeer" }],
  year: 2017,
  venue: "NeurIPS",
  citation_count: 50000,
  url: "https://arxiv.org/abs/1706.03762",
  doi: "10.5555/3295222.3295349",
  arxiv_id: null,
  keywords: [],
};

describe("BATCH-23/TASK-02: PaperCard", () => {
  // ── TEST-23-02-03: Paper card shows title, authors, year ──
  it("TEST-23-02-03: renders paper title, authors, and year", () => {
    render(<PaperCard paper={samplePaper} onIngest={vi.fn()} />);

    expect(screen.getByTestId("paper-title")).toHaveTextContent("Attention Is All You Need");
    expect(screen.getByTestId("paper-authors")).toHaveTextContent("Ashish Vaswani, Noam Shazeer");
    expect(screen.getByTestId("paper-year")).toHaveTextContent("2017");
  });

  it("renders source badge and citation count", () => {
    render(<PaperCard paper={samplePaper} onIngest={vi.fn()} />);

    expect(screen.getByText("semantic_scholar")).toBeInTheDocument();
    expect(screen.getByText(/50,000 citations/)).toBeInTheDocument();
  });

  // ── TEST-23-02-04: Ingest button requires confirmation ──
  it("TEST-23-02-04: ingest button requires two clicks (confirmation)", () => {
    const onIngest = vi.fn();
    render(<PaperCard paper={samplePaper} onIngest={onIngest} />);

    const button = screen.getByTestId("ingest-button");

    // First click: shows confirmation
    fireEvent.click(button);
    expect(onIngest).not.toHaveBeenCalled();
    expect(button).toHaveTextContent("Confirm Ingest");

    // Second click: triggers ingestion
    fireEvent.click(button);
    expect(onIngest).toHaveBeenCalledWith(samplePaper);
    expect(onIngest).toHaveBeenCalledTimes(1);
  });

  it("renders external link when URL is present", () => {
    render(<PaperCard paper={samplePaper} onIngest={vi.fn()} />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "https://arxiv.org/abs/1706.03762");
    expect(link).toHaveAttribute("target", "_blank");
  });
});
