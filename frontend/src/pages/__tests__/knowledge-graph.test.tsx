import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import KnowledgeGraphPage from "@/pages/knowledge-graph";
import type { GraphStats, GraphEntity, EntityDetail } from "@/api/knowledge-graph";

// ── Mock API ─────────────────────────────────────────────────────

vi.mock("@/api/knowledge-graph", () => ({
  getGraphStats: vi.fn(),
  getEntities: vi.fn(),
  getEntity: vi.fn(),
}));

vi.mock("@/components/knowledge-graph/graph-canvas", () => ({
  GraphCanvas: ({ entities, onSelectEntity }: { entities: GraphEntity[]; onSelectEntity: (id: string) => void }) => (
    <div data-testid="graph-canvas">
      {entities.length} entities
      <button data-testid="select-node" onClick={() => onSelectEntity(entities[0]?.id || "test:1")}>
        Select
      </button>
    </div>
  ),
}));

vi.mock("@/components/knowledge-graph/entity-detail", () => ({
  EntityDetail: ({ detail, onClose }: { detail: EntityDetail; onClose: () => void }) => (
    <div data-testid="entity-detail">
      {detail.entity.name}
      <button data-testid="close-detail" onClick={onClose}>Close</button>
    </div>
  ),
}));

import { getGraphStats, getEntities, getEntity } from "@/api/knowledge-graph";

const mockedGetGraphStats = vi.mocked(getGraphStats);
const mockedGetEntities = vi.mocked(getEntities);
const mockedGetEntity = vi.mocked(getEntity);

const sampleStats: GraphStats = {
  entity_count: 42,
  relationship_count: 78,
  entity_types: { paper: 20, author: 12, concept: 10 },
  relation_types: { cites: 50 },
};

const sampleEntities: GraphEntity[] = [
  {
    id: "concept:1",
    entity_type: "concept",
    name: "Transformer",
    aliases: [],
    properties: {},
    truth: { confidence: 0.9, frequency: 0.85, source_count: 5 },
  },
  {
    id: "paper:1",
    entity_type: "paper",
    name: "Attention Paper",
    aliases: [],
    properties: {},
    truth: { confidence: 0.95, frequency: 0.9, source_count: 8 },
  },
];

const sampleDetail: EntityDetail = {
  entity: sampleEntities[0],
  relationships: [],
};

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderPage() {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <KnowledgeGraphPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedGetGraphStats.mockResolvedValue(sampleStats);
  mockedGetEntities.mockResolvedValue(sampleEntities);
});

describe("BATCH-25/TASK-04: Knowledge Graph Page", () => {
  // ── TEST-25-04-01: Page renders with stats ────────────────────
  it("TEST-25-04-01: Page renders with stats", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Knowledge Graph")).toBeTruthy();
    });

    // Stats should be shown
    await waitFor(() => {
      expect(screen.getByText(/42 entities/)).toBeTruthy();
      expect(screen.getByText(/78 relationships/)).toBeTruthy();
    });

    // Graph canvas should render
    expect(screen.getByTestId("graph-canvas")).toBeTruthy();
  });

  // ── TEST-25-04-02: Search filters entities ────────────────────
  it("TEST-25-04-02: Search filters entities", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search entities...")).toBeTruthy();
    });

    const searchInput = screen.getByPlaceholderText("Search entities...");
    fireEvent.change(searchInput, { target: { value: "transformer" } });

    // getEntities should be called with the search term
    await waitFor(() => {
      expect(mockedGetEntities).toHaveBeenCalledWith(
        expect.objectContaining({ search: "transformer" }),
      );
    });
  });

  // ── TEST-25-04-03: Click entity shows detail panel ────────────
  it("TEST-25-04-03: Click entity shows detail panel", async () => {
    mockedGetEntity.mockResolvedValue(sampleDetail);

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("graph-canvas")).toBeTruthy();
    });

    // Simulate entity selection
    const selectBtn = screen.getByTestId("select-node");
    fireEvent.click(selectBtn);

    await waitFor(() => {
      expect(mockedGetEntity).toHaveBeenCalledWith("concept:1");
    });

    await waitFor(() => {
      expect(screen.getByTestId("entity-detail")).toBeTruthy();
      expect(screen.getByText("Transformer")).toBeTruthy();
    });

    // Close detail panel
    const closeBtn = screen.getByTestId("close-detail");
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("entity-detail")).toBeNull();
    });
  });
});
