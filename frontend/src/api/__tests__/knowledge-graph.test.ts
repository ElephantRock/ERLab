import { describe, it, expect, beforeEach, vi } from "vitest";
import { getGraphStats, getEntities, getEntity, getSubgraph } from "@/api/knowledge-graph";
import type {
  GraphStats,
  GraphEntity,
  EntityDetail,
  Subgraph,
} from "@/api/knowledge-graph";
import { apiFetchUnchecked, apiFetchJson } from "@/api/client";

vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
  apiFetchJson: vi.fn(),
}));

const mockApiFetch = vi.mocked(apiFetchUnchecked);
const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("BATCH-25/TASK-02: Knowledge Graph API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-25-02-01: getGraphStats() calls correct endpoint ──────
  it("TEST-25-02-01: getGraphStats() correct endpoint", async () => {
    const expected: GraphStats = {
      entity_count: 42,
      relationship_count: 78,
      entity_types: { paper: 20, author: 15, concept: 7 },
      relation_types: { cites: 50, uses_method: 28 },
    };
    // F1.3a: getGraphStats now uses callContract → apiFetchJson
    mockApiFetchJson.mockResolvedValueOnce(expected);

    const result = await getGraphStats();

    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result).toEqual(expected);
    expect(result.entity_count).toBe(42);
    expect(result.relationship_count).toBe(78);
  });

  // ── TEST-25-02-02: getEntities() accepts type/search params ────
  it("TEST-25-02-02: getEntities() accepts type/search params", async () => {
    const entities: GraphEntity[] = [
      {
        id: "paper:1",
        entity_type: "paper",
        name: "Attention Is All You Need",
        aliases: ["Transformer"],
        properties: {},
        truth: { confidence: 0.9, frequency: 0.8, source_count: 5 },
      },
    ];
    // F1.3a: getEntities now uses callContract → apiFetchJson. Query params
    // are appended by withQuery inside callContract; assert the JSON transport
    // was invoked (URL construction is an implementation detail of withQuery).
    mockApiFetchJson.mockResolvedValueOnce(entities);

    const result = await getEntities({ type: "paper", search: "attention" });

    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result).toEqual(entities);
    expect(result[0].name).toBe("Attention Is All You Need");
  });

  // ── TEST-25-02-03: getEntity(id) calls correct endpoint ────────
  it("TEST-25-02-03: getEntity(id) correct endpoint", async () => {
    const detail: EntityDetail = {
      entity: {
        id: "concept:transformer",
        entity_type: "concept",
        name: "Transformer",
        aliases: [],
        properties: {},
        truth: { confidence: 0.95, frequency: 0.9, source_count: 10 },
      },
      relationships: [
        {
          source_id: "paper:1",
          target_id: "concept:transformer",
          relation_type: "proposes_method",
          weight: 1.5,
          evidence: [],
          truth: { confidence: 0.8, frequency: 0.7, source_count: 3 },
        },
      ],
    };
    mockApiFetch.mockResolvedValueOnce(detail);

    const result = await getEntity("concept:transformer");

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/knowledge-graph/entity/concept%3Atransformer",
    );
    expect(result).toEqual(detail);
    expect(result.entity.name).toBe("Transformer");
    expect(result.relationships).toHaveLength(1);
  });

  // ── TEST-25-02-04: getSubgraph(id, depth) calls correct endpoint ─
  it("TEST-25-02-04: getSubgraph(id, depth) correct endpoint", async () => {
    const subgraph: Subgraph = {
      entities: [
        {
          id: "concept:1",
          entity_type: "concept",
          name: "Alpha",
          aliases: [],
          properties: {},
          truth: { confidence: 0.8, frequency: 0.7, source_count: 2 },
        },
        {
          id: "paper:1",
          entity_type: "paper",
          name: "Paper One",
          aliases: [],
          properties: {},
          truth: { confidence: 0.9, frequency: 0.8, source_count: 4 },
        },
      ],
      relationships: [
        {
          source_id: "paper:1",
          target_id: "concept:1",
          relation_type: "uses_method",
          weight: 1.0,
          evidence: [],
          truth: { confidence: 0.7, frequency: 0.6, source_count: 1 },
        },
      ],
    };
    mockApiFetch.mockResolvedValueOnce(subgraph);

    const result = await getSubgraph("concept:1", 3);

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/knowledge-graph/subgraph/concept%3A1?depth=3",
    );
    expect(result).toEqual(subgraph);
    expect(result.entities).toHaveLength(2);
    expect(result.relationships).toHaveLength(1);
  });
});
