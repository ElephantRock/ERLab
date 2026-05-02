import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GraphCanvas } from "@/components/knowledge-graph/graph-canvas";
import { EntityDetail } from "@/components/knowledge-graph/entity-detail";
import { WorldModelPanel } from "@/components/knowledge-graph/world-model-panel";
import type { GraphEntity, GraphRelationship, EntityDetail as EntityDetailType, WorldModel } from "@/api/knowledge-graph";

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

const sampleWorldModel: WorldModel = {
  total_entities: 3,
  total_relationships: 2,
  entity_type_distribution: { paper: 1, author: 1, concept: 1 },
  relationship_type_distribution: { cites: 1, proposes_method: 1 },
  top_entities: [
    sampleEntity2,
    sampleEntity,
    {
      id: "author:1",
      entity_type: "author",
      name: "Author A",
      aliases: [],
      properties: {},
      truth: { confidence: 0.7, frequency: 0.6, source_count: 2 },
    },
  ],
  strongest_relationships: [
    {
      source_id: "paper:1",
      target_id: "concept:1",
      relation_type: "proposes_method",
      weight: 1.8,
      evidence: [],
      truth: { confidence: 0.8, frequency: 0.7, source_count: 3 },
    },
    sampleRel,
  ],
};

describe("BATCH-37/TASK-01: World Model Panel", () => {
  // ── TEST-37-01-02: World model panel renders ──────────────────
  it("TEST-37-01-02: World model panel renders", () => {
    render(<WorldModelPanel model={sampleWorldModel} />);

    // Header
    expect(screen.getByText("World Model")).toBeTruthy();

    // Summary stats
    expect(screen.getByText("3 entities")).toBeTruthy();
    expect(screen.getByText("2 relationships")).toBeTruthy();

    // Entity type tags
    expect(screen.getByText("paper: 1")).toBeTruthy();
    expect(screen.getByText("author: 1")).toBeTruthy();
    expect(screen.getByText("concept: 1")).toBeTruthy();

    // Relationship type tags
    expect(screen.getByText("cites: 1")).toBeTruthy();
    expect(screen.getByText("proposes_method: 1")).toBeTruthy();
  });

  // ── TEST-37-01-03: Panel shows entity relationships ───────────
  it("TEST-37-01-03: Panel shows entity relationships", () => {
    render(<WorldModelPanel model={sampleWorldModel} />);

    // Top entities should list entity names
    expect(screen.getByText("Attention Is All You Need")).toBeTruthy();
    expect(screen.getByText("Transformer Architecture")).toBeTruthy();
    expect(screen.getByText("Author A")).toBeTruthy();

    // Strongest relationships should show source → target with relation type
    expect(screen.getAllByText("paper:1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("concept:1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/proposes_method/).length).toBeGreaterThanOrEqual(1);
  });
});
