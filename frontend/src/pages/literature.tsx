import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { searchLiterature, ingestPaper } from "@/api/literature";
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
  // F1.5b: track successfully ingested paper IDs so the production UI can
  // surface an authoritative terminal state per paper. This is client-side
  // state that becomes authoritative after the mutation's onSuccess runs
  // and the search query refetches (declared invalidation).
  const [ingestedIds, setIngestedIds] = useState<Set<string>>(new Set());

  const queryClient = useQueryClient();

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

  // F1.4.1: ingestMutation now has truthful pending, success, and failure behavior.
  // F1.5b: onSuccess also records the ingested paper id so the production UI
  // can render an authoritative "Ingested" terminal state alongside the
  // declared invalidation of ["literature-search"].
  const ingestMutation = useMutation({
    mutationFn: (paper: Paper) => ingestPaper(paper),
    retry: false,
    onSuccess: (_data, paper) => {
      toast.success(`Ingested: ${paper.title.slice(0, 50)}...`);
      setIngestedIds((prev) => new Set(prev).add(paper.id));
      queryClient.invalidateQueries({ queryKey: ["literature-search"] });
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
    // F1.5b: also refuse if this paper is already in the authoritative
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
