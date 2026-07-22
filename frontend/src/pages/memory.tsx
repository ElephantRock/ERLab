/**
 * Memory Browser Page — BATCH-19/TASK-02
 *
 * Full Memory Browser page replacing the /memory placeholder.
 * Features: search input, type filter, delete confirmation,
 * memory cards list with stats header.
 *
 * Migrated to useResource + DataView (Phase 3, Tier 3). The recall query
 * is the page's primary visible resource surface (loading/error/empty/
 * ready) — useResource + DataView. It is keyed on [activeQuery, typeFilter]
 * so changing either (search submit or type-filter change) triggers a
 * refetch via the key, replacing the previous imperative loadMemories.
 *
 * Stats is supplementary metadata (a header above the search bar), not a
 * primary surface — useQuery with an honest inline "unavailable" hint on
 * failure. The previous `console.warn("[memory] Failed to load stats")`
 * swallow silently omitted the header; now failure is visible
 * (PRODUCT.md §6, INTERFACE_CONTRACT §1/§2).
 *
 * Delete stays a mutation (local state + optimistic cache update via
 * queryClient.setQueryData + stats invalidation), matching the original
 * behavior.
 */

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getMemoryStats, recallMemories, deleteMemory } from "@/api/memory";
import type {
  MemoryRecallResult,
  MemoryRecallResponse,
} from "@/api/memory";
import { toast } from "sonner";
import { MemoryCard } from "@/components/memory/memory-card";
import { MemoryStats } from "@/components/memory/memory-stats";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { DataView } from "@/components/ui/data-view";
import { useResource } from "@/lib/useResource";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, AlertCircle } from "lucide-react";

const MEMORY_TYPES = ["semantic", "episodic", "procedural"] as const;
const BROAD_QUERY = "*";
const DEFAULT_TOP_K = 50;

export default function MemoryBrowserPage() {
  const queryClient = useQueryClient();

  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState(BROAD_QUERY);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Delete confirmation state (mutation UI, stays local)
  const [confirmDelete, setConfirmDelete] = useState<MemoryRecallResult | null>(null);
  // Mutation 13: pending state for delete confirmation button
  const [isDeleting, setIsDeleting] = useState(false);

  // ── Stats (supplementary metadata, useQuery + honest fallback) ──
  // Previously .catch(console.warn) silently omitted the header on failure.
  // Now isError drives an honest "unavailable" hint (PRODUCT.md §6).
  const RECALL_KEY = ["memory", "recall", activeQuery, typeFilter] as const;
  const { data: stats, isError: statsError } = useQuery({
    queryKey: ["memory", "stats"],
    queryFn: () => getMemoryStats(),
  });

  // ── Recall (primary visible surface, useResource + DataView) ────
  // Keyed on [activeQuery, typeFilter] — changing either (via search
  // submit or filter change) triggers a refetch through the key.
  const recallResource = useResource<MemoryRecallResponse>(
    RECALL_KEY,
    () => {
      const params: { memory_type?: string; top_k?: number } = {
        top_k: DEFAULT_TOP_K,
      };
      if (typeFilter !== "all") {
        params.memory_type = typeFilter;
      }
      return recallMemories(activeQuery, params);
    },
    { isEmpty: (d) => d.results.length === 0 },
  );

  // ── Search handler ─────────────────────────────────────────────
  // Updates activeQuery → the recall resource's key changes → refetch.
  function handleSearch() {
    const q = query.trim() || BROAD_QUERY;
    setActiveQuery(q);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      handleSearch();
    }
  }

  // ── Type filter handler ────────────────────────────────────────
  // Updates typeFilter → the recall resource's key changes → refetch.
  function handleTypeChange(value: string) {
    setTypeFilter(value);
  }

  // ── Delete handler (mutation + optimistic cache update) ────────
  // Mutation 13: track isDeleting to disable the confirm button while the
  // delete is in flight (F1.4.1/F1.4.2 pattern). The setQueryData removal
  // is post-success (after await), so it remains correct.
  async function handleDeleteConfirm() {
    if (!confirmDelete) return;
    if (isDeleting) return;
    const target = confirmDelete;
    setIsDeleting(true);
    try {
      await deleteMemory(target.content);
      // Optimistic removal from the recall cache — matches the original
      // setResults(prev => prev.filter(...)).
      queryClient.setQueryData<MemoryRecallResponse>(RECALL_KEY, (prev) =>
        prev
          ? { ...prev, results: prev.results.filter((m) => m !== target) }
          : prev,
      );
      // Refresh stats after deletion.
      queryClient.invalidateQueries({ queryKey: ["memory", "stats"] });
      setConfirmDelete(null);
    } catch (err) {
      toast.error("Failed to delete memory item");
      setIsDeleting(false);
    }
  }

  function handleDeleteRequest(memory: MemoryRecallResult) {
    setConfirmDelete(memory);
  }

  function handleDeleteCancel() {
    setConfirmDelete(null);
  }

  return (
    <div className="space-y-6" data-testid="memory-page">
      <h1 className="text-2xl font-bold tracking-tight">Memory Browser</h1>

      {/* Stats Header — supplementary. Failed fetch shows honest "unavailable"
          rather than silently omitting the header (PRODUCT.md §6). */}
      {statsError ? (
        <div
          className="rounded-lg border border-warning/30 bg-banner-warning-bg p-3 text-sm text-warning"
          data-testid="stats-header"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <span>Memory stats unavailable.</span>
          </div>
        </div>
      ) : stats ? (
        <div data-testid="stats-header">
          <MemoryStats stats={stats} />
        </div>
      ) : null}

      {/* Search & Filter Bar */}
      <div className="flex gap-3 items-center" data-testid="search-bar">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search memories..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-9"
            data-testid="search-input"
          />
        </div>
        <Select value={typeFilter} onValueChange={handleTypeChange}>
          <SelectTrigger className="w-[160px]" data-testid="type-filter">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {MEMORY_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={handleSearch} data-testid="search-btn">
          Search
        </Button>
      </div>

      {/* Delete Confirmation Dialog */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          data-testid="delete-confirm-dialog"
        >
          <div className="bg-background rounded-lg border p-6 max-w-md mx-4 shadow-lg">
            <h3 className="font-semibold text-lg mb-2">Delete Memory</h3>
            <p className="text-sm text-muted-foreground mb-1">
              Are you sure you want to delete this memory?
            </p>
            <p className="text-sm bg-muted rounded p-3 mb-4 line-clamp-3">
              {confirmDelete.content}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={handleDeleteCancel} disabled={isDeleting}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
                data-testid="confirm-delete-btn"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Results — primary visible surface, DataView handles all 4 states */}
      <DataView
        resource={recallResource}
        testId="memory"
        loading={{ lines: 3 }}
        error={{ message: "Error loading memories" }}
        empty={{
          what: "memories",
          message: "Try adjusting your search query or filters.",
        }}
      >
        {(data) => (
          <div className="space-y-3">
            {data.results.map((memory, idx) => (
              <MemoryCard
                key={`${memory.content}-${idx}`}
                memory={memory}
                onDelete={handleDeleteRequest}
              />
            ))}
          </div>
        )}
      </DataView>
    </div>
  );
}
