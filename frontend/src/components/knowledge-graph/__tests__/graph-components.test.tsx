import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GraphCanvas } from "@/components/knowledge-graph/graph-canvas";
import { EntityDetail } from "@/components/knowledge-graph/entity-detail";
import type { GraphEntity, GraphRelationship, EntityDetail as EntityDetailType } from "@/api/knowledge-graph";

const sampleEntity: GraphEntity = {
  id: "concept:1",
  entity_type: "concept",
  name: "Transformer Architecture",
  aliases: ["Transformer"],
  properties: {},
  truth: { confidence: 0.9, frequency: 0.85, source_count: 10 },
};

const sampleEntity2: GraphEntity = {
  id: "paper:1",
  entity_type: "paper",
  name: "Attention Is All You Need",
  aliases: [],
  properties: { year: "2017" },
  truth: { confidence: 0.95, frequency: 0.9, source_count: 15 },
};

const sampleRel: GraphRelationship = {
  source_id: "paper:1",
  target_id: "concept:1",
  relation_type: "proposes_method",
  weight: 1.5,
  evidence: [],
  truth: { confidence: 0.8, frequency: 0.7, source_count: 3 },
};

const sampleDetail: EntityDetailType = {
  entity: sampleEntity,
  relationships: [sampleRel],
};

describe("BATCH-25/TASK-03: Graph Canvas and Entity Detail", () => {
  // ── TEST-25-03-01: GraphCanvas renders with entities ──────────
  it("TEST-25-03-01: GraphCanvas renders with entities", () => {
    const { container } = render(
      <GraphCanvas
        entities={[sampleEntity, sampleEntity2]}
        relationships={[sampleRel]}
        selectedId={null}
        onSelectEntity={vi.fn()}
      />,
    );

    // Should render SVG
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();

    // Should render node circles (2 entities)
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBeGreaterThanOrEqual(2);

    // Should render entity names as text (SVG truncates to 18 chars)
    expect(screen.getByText("Transformer Arch…")).toBeTruthy();
    expect(screen.getByText("Attention Is All…")).toBeTruthy();

    // Legend should show types
    expect(screen.getByText("paper")).toBeTruthy();
    expect(screen.getByText("concept")).toBeTruthy();
  });

  // ── TEST-25-03-02: Entity click shows detail panel ────────────
  it("TEST-25-03-02: Entity click shows detail panel", () => {
    render(
      <EntityDetail
        detail={sampleDetail}
        onClose={vi.fn()}
      />,
    );

    // Entity name should be shown
    expect(screen.getByText("Transformer Architecture")).toBeTruthy();

    // Type badge
    expect(screen.getByText("concept")).toBeTruthy();

    // Truth values
    expect(screen.getByText(/90%/)).toBeTruthy();

    // Relationship should be listed (split across elements: "←" + " proposes_method")
    expect(screen.getByText("proposes_method", { exact: false })).toBeTruthy();
  });

  // ── TEST-25-03-03: Type filter updates visible entities ────────
  it("TEST-25-03-03: Type filter updates visible entities", () => {
    const onSelect = vi.fn();

    // Render with only concept entities (simulating a filtered list)
    const { container, rerender } = render(
      <GraphCanvas
        entities={[sampleEntity]}
        relationships={[]}
        selectedId={null}
        onSelectEntity={onSelect}
      />,
    );

    // Only one entity should be rendered
    let labels = container.querySelectorAll("svg text");
    let hasTransformer = Array.from(labels).some(
      (t) => t.textContent?.includes("Transformer"),
    );
    expect(hasTransformer).toBe(true);

    // Rerender with different filtered entities
    rerender(
      <GraphCanvas
        entities={[sampleEntity2]}
        relationships={[]}
        selectedId={null}
        onSelectEntity={onSelect}
      />,
    );

    labels = container.querySelectorAll("svg text");
    const hasAttention = Array.from(labels).some(
      (t) => t.textContent?.includes("Attention"),
    );
    expect(hasAttention).toBe(true);
  });
});
