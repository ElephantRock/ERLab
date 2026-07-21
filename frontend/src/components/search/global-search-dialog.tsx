import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Lightbulb, GitBranch, BookMarked, Play, Search } from "lucide-react";
import { globalSearch } from "@/api/search";
import { toast } from "sonner";
import type {
  GlobalSearchResponse,
} from "@/api/types";

const STORAGE_KEY = "erock:recent-searches";
const MAX_RECENT = 10;
const DEBOUNCE_MS = 300;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function getRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function addRecentSearch(query: string) {
  const recent = getRecentSearches().filter((s) => s !== query);
  recent.unshift(query);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
}

export function GlobalSearchDialog({ open, onOpenChange }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GlobalSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const navigate = useNavigate();

  // Auto-focus input when dialog opens
  useEffect(() => {
    if (open) {
      // Small delay so the DOM is ready
      const timer = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    } else {
      setQuery("");
      setResults(null);
      setLoading(false);
    }
  }, [open]);

  // Debounced search
  const doSearch = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setResults(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await globalSearch(q);
        setResults(res);
      } catch (err) {
        toast.error("Search failed \u2014 please try again");
        setResults(null);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  function handleInputChange(value: string) {
    setQuery(value);
    doSearch(value);
  }

  function handleSelect(type: string, id: number) {
    addRecentSearch(query);
    onOpenChange(false);
    switch (type) {
      case "ideas":
        navigate(`/ideas/${id}`);
        break;
      case "gaps":
        navigate(`/gaps/${id}`);
        break;
      case "papers":
        navigate(`/literature?q=${encodeURIComponent(query)}`);
        break;
      case "runs":
        navigate(`/runs/${id}`);
        break;
    }
  }

  function handleRecentClick(recent: string) {
    setQuery(recent);
    doSearch(recent);
  }

  const recentSearches = !query ? getRecentSearches() : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl p-0 overflow-hidden">
        <div className="flex items-center border-b px-3">
          <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            placeholder="Search ideas, gaps, papers, runs..."
            className="flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground"
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
          />
        </div>
        <div className="max-h-80 overflow-y-auto px-2 py-2">
          {/* Loading skeletons */}
          {loading && (
            <div className="space-y-2 px-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 p-2">
                  <Skeleton className="h-4 w-4 rounded" />
                  <Skeleton className="h-4 flex-1" />
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {!loading && !results && recentSearches.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Start typing to search...
            </p>
          )}

          {/* Recent searches */}
          {!loading && !results && recentSearches.length > 0 && (
            <div className="px-2">
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Recent
              </p>
              {recentSearches.map((s) => (
                <button
                  key={s}
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent text-left"
                  onClick={() => handleRecentClick(s)}
                >
                  <Search className="h-3 w-3 text-muted-foreground" />
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Results */}
          {!loading && results && results.total === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No results found for "{query}"
            </p>
          )}

          {!loading && results && results.total > 0 && (
            <div className="space-y-3 px-2">
              {results.results.ideas && results.results.ideas.items.length > 0 && (
                <ResultGroup
                  label="Ideas"
                  icon={<Lightbulb className="h-4 w-4 text-warning" />}
                  items={results.results.ideas.items.map((item) => ({
                    id: item.id,
                    title: item.title,
                    secondary: `${item.domain} · ${item.overall_score != null ? `Score: ${(item.overall_score * 100).toFixed(0)}%` : 'Not scored'}`,
                  }))}
                  type="ideas"
                  onSelect={handleSelect}
                />
              )}
              {results.results.gaps && results.results.gaps.items.length > 0 && (
                <ResultGroup
                  label="Gaps"
                  icon={<GitBranch className="h-4 w-4 text-info" />}
                  items={results.results.gaps.items.map((item) => ({
                    id: item.id,
                    title: item.title,
                    secondary: `${item.gap_type} · Confidence: ${item.confidence}`,
                  }))}
                  type="gaps"
                  onSelect={handleSelect}
                />
              )}
              {results.results.papers && results.results.papers.items.length > 0 && (
                <ResultGroup
                  label="Papers"
                  icon={<BookMarked className="h-4 w-4 text-success" />}
                  items={results.results.papers.items.map((item) => ({
                    id: item.id,
                    title: item.title,
                    secondary: `${item.year} · ${item.venue}`,
                  }))}
                  type="papers"
                  onSelect={handleSelect}
                />
              )}
              {results.results.runs && results.results.runs.items.length > 0 && (
                <ResultGroup
                  label="Runs"
                  icon={<Play className="h-4 w-4 text-info" />}
                  items={results.results.runs.items.map((item) => ({
                    id: item.id,
                    title: `Run #${item.id}`,
                    secondary: `${item.status} · ${item.domain}`,
                  }))}
                  type="runs"
                  onSelect={handleSelect}
                />
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface ResultGroupProps {
  label: string;
  icon: React.ReactNode;
  items: { id: number; title: string; secondary: string }[];
  type: string;
  onSelect: (type: string, id: number) => void;
}

function ResultGroup({ label, icon, items, type, onSelect }: ResultGroupProps) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      {items.map((item) => (
        <button
          key={`${type}-${item.id}`}
          className="flex w-full items-center gap-3 rounded-sm px-2 py-1.5 text-sm hover:bg-accent text-left"
          onClick={() => onSelect(type, item.id)}
        >
          {icon}
          <div className="flex-1 min-w-0">
            <div className="truncate font-medium">{item.title}</div>
            <div className="truncate text-xs text-muted-foreground">
              {item.secondary}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
