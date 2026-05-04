/**
 * BATCH-63/TASK-02: TreeVisualization component tests.
 *
 * TEST-63-02-01: Renders tree nodes from tree_data prop
 * TEST-63-02-02: Shows "No tree data" message when tree_data is null
 * TEST-63-02-03: Highlights top-scored node
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TreeVisualization } from "@/components/pipeline/tree-visualization";
import type { TreeData } from "@/api/types";

// ── Fixtures ────────────────────────────────────────────────────

const sampleTreeData: TreeData = {
  engine: "tree_search",
  config: {
    beam_width: 2,
    max_depth: 3,
    ideas_per_node: 3,
  },
  nodes: [
    {
      id: "root-1",
      title: "Root Idea: Attention Mechanisms",
      score: 0.5,
      proposed_method: "Apply attention to cross-domain problems",
      parent_ids: [],
    },
    {
      id: "child-1",
      title: "Sparse Attention for NLP",
      score: 0.8,
      proposed_method: "Use sparse attention patterns for efficiency",
      parent_ids: ["root-1"],
    },
    {
      id: "child-2",
      title: "Multi-Head Attention for Vision",
      score: 0.6,
      proposed_method: "Adapt multi-head attention for image classification",
      parent_ids: ["root-1"],
    },
    {
      id: "leaf-1",
      title: "Pruned Sparse Transformer",
      score: 0.3,
      proposed_method: "Prune attention heads dynamically",
      parent_ids: ["child-1"],
    },
  ],
};

describe("BATCH-63/TASK-02: TreeVisualization", () => {
  // ── TEST-63-02-01: Renders tree nodes from tree_data prop ────
  it("TEST-63-02-01: renders tree nodes from tree_data prop", () => {
    const { container } = render(
      <TreeVisualization tree_data={sampleTreeData} />,
    );

    // Should render SVG
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();

    // Should render node rectangles (4 nodes in sample data)
    const rects = container.querySelectorAll("rect");
    expect(rects.length).toBeGreaterThanOrEqual(4);

    // Should render edge lines connecting parent→child
    const lines = container.querySelectorAll("line");
    expect(lines.length).toBeGreaterThanOrEqual(3); // root→child1, root→child2, child1→leaf1

    // Should have node titles as text elements
    const texts = container.querySelectorAll("svg text");
    const allText = Array.from(texts).map((t) => t.textContent).join(" ");
    expect(allText).toContain("Root Idea");
    expect(allText).toContain("Sparse Attention");

    // Should have data-testid on the container
    expect(container.querySelector('[data-testid="tree-visualization"]')).toBeTruthy();
  });

  // ── TEST-63-02-02: Shows "No tree data" when tree_data is null ─
  it("TEST-63-02-02: shows 'No tree data' message when tree_data is null", () => {
    render(<TreeVisualization tree_data={null} />);

    expect(screen.getByTestId("tree-empty")).toBeTruthy();
    expect(screen.getByText(/No tree data available/)).toBeTruthy();
  });

  // ── TEST-63-02-03: Highlights top-scored node ────────────────
  it("TEST-63-02-03: highlights top-scored node", () => {
    const { container } = render(
      <TreeVisualization tree_data={sampleTreeData} />,
    );

    // The top-scored node (child-1, score 0.8) should have a highlight rect
    const topHighlight = container.querySelector('[data-testid="top-scored-node"]');
    expect(topHighlight).toBeTruthy();

    // The highlight should be a rect element with a blue stroke
    expect(topHighlight?.tagName.toLowerCase()).toBe("rect");
    expect(topHighlight?.getAttribute("stroke")).toBe("#3b82f6");

    // Only one node should be highlighted as top
    const allHighlights = container.querySelectorAll('[data-testid="top-scored-node"]');
    expect(allHighlights.length).toBe(1);
  });

  // ── Additional: hover shows tooltip ──────────────────────────
  it("shows tooltip on node hover", () => {
    const { container } = render(
      <TreeVisualization tree_data={sampleTreeData} />,
    );

    // Hover over a node
    const node = container.querySelector('[data-testid^="tree-node-"]');
    expect(node).toBeTruthy();

    fireEvent.mouseEnter(node!);

    // Tooltip should appear with node title
    const tooltip = screen.queryByTestId("tree-tooltip");
    expect(tooltip).toBeTruthy();
  });
});
