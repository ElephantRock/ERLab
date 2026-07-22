import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { searchLiterature, ingestPaper, listIngestedPapers } from "@/api/literature";
import { PaperCard } from "@/components/literature/paper-card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, BookOpen, Inbox } from "lucide-react";
import { ErrorCard } from "@/components/ui/error-card";
import { EmptyState } from "@/components/ui/empty-state";
import { toast } from "sonner";
import type { Paper } from "@/api/literature";

export default function LiteraturePage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
  const [urlParams] = useSearchParams();

  // Auto-search from URL param (e.g., from global search navigation)
  useEffect(() => {
    const q = urlParams.get("q");
    if (q && q.trim()) {
      setQuery(q);
      setSubmittedQuery(q);
    }
  }, [urlParams]);

  const {
    data: searchData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["literature-search", submittedQuery],
    queryFn: () => searchLiterature(submittedQuery!),
    enabled: !!submittedQuery,
  });

  // F1.5c: backend-derived persisted ingestion state.
  // The "Ingested" badge is derived from this query's response, NOT from
  // ephemeral client state. The mutation's onSuccess invalidates this key,
  // so the badge always reflects backend truth and survives reload/remount.
  const { data: ingestedData } = useQuery({
    queryKey: ["literature-ingested"],
    queryFn: () => listIngestedPapers(),
  });
  const ingestedIds = new Set(ingestedData?.ids ?? []);

  // F1.4.1 + F1.5c: ingest mutation.
  // - retry: false (non-idempotent POST)
  // - meta.invalidatePrefixes: ["literature-search"] (refresh all cached
  //   searches) — cache-owned, survives unmount.
  // - meta.invalidateQueries: ["literature-ingested"] (the authoritative
  //   backend-derived ingested-ids list that drives the badge) —
  //   cache-owned, survives unmount.
  // - onSuccess/onError: component-level toasts (UX feedback only).
  //   The badge itself is NOT local state — it derives from the refetched
  //   ["literature-ingested"] response.
  const ingestMutation = useMutation({
    mutationFn: (paper: Paper) => ingestPaper(paper),
    retry: false,
    mutationKey: ["literature", "ingest"],
    meta: {
      invalidatePrefixes: [["literature-search"]],
      invalidateQueries: [["literature-ingested"]],
    },
    onSuccess: (_data, paper) => {
      toast.success(`Ingested: ${paper.title.slice(0, 50)}...`);
    },
    onError: (_error, paper) => {
      toast.error(`Failed to ingest: ${paper.title.slice(0, 50)}...`);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSubmittedQuery(query.trim());
  }

  function handleIngest(paper: Paper) {
    // F1.4.1: prevent duplicate submission — disable while pending
    if (ingestMutation.isPending) return;
    // F1.5c: also refuse if this paper is already in the backend-authoritative
    // ingested set (terminal state).
    if (ingestedIds.has(paper.id)) return;
    ingestMutation.mutate(paper);
  }

  const papers = searchData?.papers ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Literature Search</h1>
        <p className="text-muted-foreground">
          Search across Semantic Scholar, arXiv, and OpenAlex for academic papers.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search papers by topic, author, or keyword..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
          data-testid="literature-search-input"
        />
      </form>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorCard message="Search failed. Please try again." testId="search-error" />
      ) : submittedQuery && papers.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No papers found"
          message={`No matches for "${submittedQuery}".`}
          testId="no-results"
        />
      ) : papers.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            <BookOpen className="h-4 w-4 inline mr-1" />
            {papers.length} paper{papers.length !== 1 ? "s" : ""} for &quot;{submittedQuery}&quot;
          </p>
          {papers.map((paper) => (
            <PaperCard
              key={paper.id}
              paper={paper}
              onIngest={handleIngest}
              isIngesting={ingestMutation.isPending && ingestMutation.variables?.id === paper.id}
              isIngested={ingestedIds.has(paper.id)}
              ingestError={ingestMutation.isError && ingestMutation.variables?.id === paper.id
                ? "Ingest failed"
                : undefined}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
