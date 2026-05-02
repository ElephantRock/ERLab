/**
 * KnowledgeGraphPage — interactive graph explorer.
 *
 * Features: stats bar, type filter, search, SVG graph canvas, entity detail panel.
 * HB-02: Initial render limited to 100 entities.
 */

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Search, Filter, Loader2 } from "lucide-react";
import { getGraphStats, getEntities, getEntity } from "@/api/knowledge-graph";
import type { GraphStats, GraphEntity, EntityDetail } from "@/api/knowledge-graph";
import { GraphCanvas } from "@/components/knowledge-graph/graph-canvas";
import { EntityDetail as EntityDetailPanel } from "@/components/knowledge-graph/entity-detail";

const ENTITY_TYPES = ["paper", "author", "method", "dataset", "concept"];

export default function KnowledgeGraphPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<EntityDetail | null>(null);

  // ── Stats query ───────────────────────────────────────────────
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["knowledge-graph-stats"],
    queryFn: () => getGraphStats(),
  });

  // ── Entities query (HB-02: max 100) ──────────────────────────
  const { data: entities, isLoading: entitiesLoading } = useQuery({
    queryKey: ["knowledge-graph-entities", typeFilter, searchTerm],
    queryFn: () =>
      getEntities({
        type: typeFilter || undefined,
        search: searchTerm || undefined,
        limit: 100,
      }),
  });

  // ── Derive relationships from entity detail for the canvas ───
  const relationships = detailData?.relationships || [];

  // ── Entity detail query ──────────────────────────────────────
  const handleSelectEntity = useCallback(
    async (id: string) => {
      setSelectedId(id);
      try {
        const detail = await getEntity(id);
        setDetailData(detail);
      } catch {
        // Silently handle — detail panel stays hidden
      }
    },
    [],
  );

  const handleCloseDetail = useCallback(() => {
    setSelectedId(null);
    setDetailData(null);
  }, []);

  const handleNavigateToEntity = useCallback(
    (id: string) => {
      handleSelectEntity(id);
    },
    [handleSelectEntity],
  );

  const isLoading = statsLoading || entitiesLoading;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <BrainCircuit className="h-6 w-6" />
          Knowledge Graph
        </h1>
        <p className="text-muted-foreground">
          Explore entities and their relationships in the knowledge graph.
        </p>
      </div>

      {/* Stats Bar */}
      {stats && (
        <div className="flex gap-4 text-sm">
          <span className="px-3 py-1 rounded-md bg-primary/10 text-primary font-medium">
            {stats.entity_count} entities
          </span>
          <span className="px-3 py-1 rounded-md bg-primary/10 text-primary font-medium">
            {stats.relationship_count} relationships
          </span>
          {Object.entries(stats.entity_types).map(
            ([type, count]) =>
              count > 0 && (
                <span key={type} className="px-2 py-1 rounded-md bg-muted text-muted-foreground">
                  {type}: {count}
                </span>
              ),
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search entities..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border rounded-md bg-background"
          />
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-sm border rounded-md px-2 py-2 bg-background"
          >
            <option value="">All types</option>
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main content */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          Loading graph...
        </div>
      ) : entities && entities.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Graph Canvas (HB-01: client-side SVG) */}
          <div className={detailData ? "lg:col-span-2" : "lg:col-span-3"}>
            <GraphCanvas
              entities={entities}
              relationships={relationships}
              selectedId={selectedId}
              onSelectEntity={handleSelectEntity}
              className="h-[500px]"
            />
          </div>

          {/* Entity Detail Panel */}
          {detailData && (
            <div className="lg:col-span-1">
              <EntityDetailPanel
                detail={detailData}
                onClose={handleCloseDetail}
                onNavigateToEntity={handleNavigateToEntity}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <BrainCircuit className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p>No entities found. Ingest papers to populate the knowledge graph.</p>
        </div>
      )}
    </div>
  );
}
