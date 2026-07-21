/**
 * KnowledgeGraphPage — interactive graph explorer.
 *
 * Features: stats bar, type filter, search, SVG graph canvas, entity detail panel.
 * HB-02: Initial render limited to 100 entities.
 *
 * Entity-detail fetch migrated from a hand-rolled `handleSelectEntity` +
 * `console.warn` swallow to a dependent react-query. Uses `useQuery`
 * directly (NOT `useResource`) per INTERFACE_CONTRACT §1's decision rule:
 * the detail panel is a dependent subquery keyed off the graph's
 * selection state — it opens on click and renders inline, with no
 * separate loading/error/empty panel of its own. Forcing `useResource`
 * + `<DataView>` here would invent a 4-state panel the interaction does
 * not have. The page-level resources (stats, entities, world model) are
 * already react-query; the detail is one more query in the same family.
 *
 * The previous `console.warn("[knowledge-graph] Failed to load entity")`
 * swallow is gone — a failed detail fetch now surfaces a toast (the
 * contract's on-demand-failure convention, INTERFACE_CONTRACT §2) and the
 * panel stays closed rather than silently doing nothing.
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Search, Filter, Loader2 } from "lucide-react";
import { getGraphStats, getEntities, getEntity, getWorldModel } from "@/api/knowledge-graph";
import { GraphCanvas } from "@/components/knowledge-graph/graph-canvas";
import { EntityDetail as EntityDetailPanel } from "@/components/knowledge-graph/entity-detail";
import { WorldModelPanel } from "@/components/knowledge-graph/world-model-panel";
import { toast } from "sonner";

const ENTITY_TYPES = ["paper", "author", "method", "dataset", "concept"];

export default function KnowledgeGraphPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // ── World model query ────────────────────────────────────────
  const { data: worldModel, isError: worldModelError } = useQuery({
    queryKey: ["knowledge-graph-world-model"],
    queryFn: () => getWorldModel(),
  });

  // ── Stats query ───────────────────────────────────────────────
  const { data: stats, isLoading: statsLoading, isError: statsError } = useQuery({
    queryKey: ["knowledge-graph-stats"],
    queryFn: () => getGraphStats(),
  });

  // ── Entities query (HB-02: max 100) ──────────────────────────
  const {
    data: entities,
    isLoading: entitiesLoading,
    isError: entitiesError,
    refetch: refetchEntities,
  } = useQuery({
    queryKey: ["knowledge-graph-entities", typeFilter, searchTerm],
    queryFn: () =>
      getEntities({
        type: typeFilter || undefined,
        search: searchTerm || undefined,
        limit: 100,
      }),
  });

  // ── Entity detail query (dependent subquery) ─────────────────
  // Fires only when an entity is selected; auto-cancels and re-fires on
  // selection change. Replaces the previous hand-rolled fetch + swallow.
  const { data: detailData, isError: detailError } = useQuery({
    queryKey: ["kg-entity", selectedId],
    queryFn: () => getEntity(selectedId!),
    enabled: !!selectedId,
  });

  // Surface detail-fetch failures as a toast. Previously the failure was
  // swallowed (console.warn) and the panel silently never opened.
  // useEffect keeps this side-effect out of render.
  // Note: this is a side-effect, not a state mutation — react-query keeps
  // the failed query in cache; the panel just doesn't open on error.
  const handleSelectEntity = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  // Toast on detail error. Kept as an effect rather than inside
  // handleSelectEntity because the query can also fail on refetch, not
  // just initial selection — the effect catches both.
  useDetailErrorToast(detailError, selectedId);

  const handleCloseDetail = useCallback(() => {
    setSelectedId(null);
  }, []);

  const handleNavigateToEntity = useCallback(
    (id: string) => {
      handleSelectEntity(id);
    },
    [handleSelectEntity],
  );

  const isLoading = statsLoading || entitiesLoading;

  // Derive relationships from the selected entity detail for the canvas.
  const relationships = detailData?.relationships || [];

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
      {statsError && (
        <div className="text-sm text-destructive" data-testid="kg-stats-error">
          Failed to load graph stats.
        </div>
      )}

      {/* World Model Panel */}
      {worldModelError ? (
        <div className="text-sm text-destructive" data-testid="kg-world-model-error">
          Failed to load world model.
        </div>
      ) : worldModel ? (
        <WorldModelPanel model={worldModel} />
      ) : null}

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
      ) : entitiesError ? (
        <div
          className="text-center py-12 text-sm text-destructive"
          data-testid="kg-entities-error"
        >
          Failed to load entities.{" "}
          <button onClick={() => refetchEntities()} className="underline">
            Retry
          </button>
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

          {/* Entity Detail Panel — only renders when the detail query has data. */}
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

/**
 * Toast-on-detail-error effect. Extracted as a hook so the render path
 * stays free of side effects. Fires once when `isError` flips true for a
 * given selection; tracks the last-reported selection to avoid duplicate
 * toasts on re-render.
 */
function useDetailErrorToast(isError: boolean, selectedId: string | null) {
  const [lastReported, setLastReported] = useState<string | null>(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- minimal effect; deps intentionally narrow
  useEffect(() => {
    if (isError && selectedId && selectedId !== lastReported) {
      toast.error("Failed to load entity detail");
      setLastReported(selectedId);
    }
    if (!isError && lastReported) {
      setLastReported(null);
    }
  });
}
