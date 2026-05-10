/**
 * Memory Browser Page — BATCH-19/TASK-02
 *
 * Full Memory Browser page replacing the /memory placeholder.
 * Features: search input, type filter, delete confirmation,
 * memory cards list with stats header.
 */

import { useCallback, useEffect, useState } from "react";
import { getMemoryStats, recallMemories, deleteMemory } from "@/api/memory";
import type { MemoryStats as MemoryStatsData, MemoryRecallResult } from "@/api/memory";
import { toast } from "sonner";
import { MemoryCard } from "@/components/memory/memory-card";
import { MemoryStats } from "@/components/memory/memory-stats";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, Loader2, AlertCircle } from "lucide-react";

const MEMORY_TYPES = ["semantic", "episodic", "procedural"] as const;
const BROAD_QUERY = "*";
const DEFAULT_TOP_K = 50;

export default function MemoryBrowserPage() {
  const [stats, setStats] = useState<MemoryStatsData | null>(null);
  const [results, setResults] = useState<MemoryRecallResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState(BROAD_QUERY);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Delete confirmation state
  const [confirmDelete, setConfirmDelete] = useState<MemoryRecallResult | null>(null);

  // ── Load stats ─────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    try {
      const data = await getMemoryStats();
      setStats(data);
    } catch (err) {
      console.warn("[memory] Failed to load stats:", err);
    }
  }, []);

  // ── Recall memories ────────────────────────────────────────────
  const loadMemories = useCallback(
    async (searchQuery: string, memType?: string) => {
      setLoading(true);
      setError(null);
      try {
        const params: { memory_type?: string; top_k?: number } = {
          top_k: DEFAULT_TOP_K,
        };
        if (memType && memType !== "all") {
          params.memory_type = memType;
        }
        const data = await recallMemories(searchQuery || BROAD_QUERY, params);
        setResults(data.results);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load memories");
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // ── Initial load ───────────────────────────────────────────────
  useEffect(() => {
    loadStats();
    loadMemories(BROAD_QUERY);
  }, [loadStats, loadMemories]);

  // ── Search handler ─────────────────────────────────────────────
  function handleSearch() {
    const q = query.trim() || BROAD_QUERY;
    setActiveQuery(q);
    loadMemories(q, typeFilter);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      handleSearch();
    }
  }

  // ── Type filter handler ────────────────────────────────────────
  function handleTypeChange(value: string) {
    setTypeFilter(value);
    loadMemories(activeQuery, value);
  }

  // ── Delete handler ─────────────────────────────────────────────
  function handleDeleteRequest(memory: MemoryRecallResult) {
    setConfirmDelete(memory);
  }

  async function handleDeleteConfirm() {
    if (!confirmDelete) return;

    try {
      await deleteMemory(confirmDelete.content);
      setResults((prev) => prev.filter((m) => m !== confirmDelete));
      // Refresh stats after deletion
      loadStats();
    } catch (err) {
      toast.error("Failed to delete memory item");
    } finally {
      setConfirmDelete(null);
    }
  }

  function handleDeleteCancel() {
    setConfirmDelete(null);
  }

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="space-y-6" data-testid="memory-page">
      <h1 className="text-2xl font-bold tracking-tight">Memory Browser</h1>

      {/* Stats Header */}
      {stats && (
        <div data-testid="stats-header">
          <MemoryStats stats={stats} />
        </div>
      )}

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

      {/* Loading State */}
      {loading && (
        <div className="flex items-center gap-2 text-muted-foreground" data-testid="loading-state">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading memories...</span>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div
          className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800"
          data-testid="error-state"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            <p className="font-medium">Error loading memories</p>
          </div>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

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
              <Button variant="outline" onClick={handleDeleteCancel}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDeleteConfirm} data-testid="confirm-delete-btn">
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {!loading && !error && (
        <div data-testid="results-list">
          {results.length === 0 ? (
            <div className="text-center py-12" data-testid="empty-state">
              <p className="text-muted-foreground text-lg">No memories found</p>
              <p className="text-sm text-muted-foreground mt-1">
                Try adjusting your search query or filters.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((memory, idx) => (
                <MemoryCard
                  key={`${memory.content}-${idx}`}
                  memory={memory}
                  onDelete={handleDeleteRequest}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
