import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { searchLiterature, ingestPaper } from "@/api/literature";
import { PaperCard } from "@/components/literature/paper-card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, BookOpen, AlertCircle, Inbox } from "lucide-react";
import type { Paper } from "@/api/literature";

export default function LiteraturePage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
  const [urlParams] = useSearchParams();

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

  const ingestMutation = useMutation({
    mutationFn: (paper: Paper) => ingestPaper(paper),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["literature-search"] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSubmittedQuery(query.trim());
  }

  function handleIngest(paper: Paper) {
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
        <div className="text-center py-12 text-destructive">
          <AlertCircle className="h-8 w-8 mx-auto mb-2 opacity-70" />
          <p data-testid="search-error">Search failed. Please try again.</p>
        </div>
      ) : submittedQuery && papers.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Inbox className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p data-testid="no-results">No papers found for &quot;{submittedQuery}&quot;.</p>
        </div>
      ) : papers.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            <BookOpen className="h-4 w-4 inline mr-1" />
            {papers.length} paper{papers.length !== 1 ? "s" : ""} for &quot;{submittedQuery}&quot;
          </p>
          {papers.map((paper) => (
            <PaperCard key={paper.id} paper={paper} onIngest={handleIngest} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
