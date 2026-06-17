import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { searchKnowledge, getKnowledgeStats } from "@/api/knowledge";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, Database, AlertCircle, FileText, Layers } from "lucide-react";
import { ErrorCard } from "@/components/ui/error-card";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { UploadZone } from "@/components/knowledge/upload-zone";

function distanceColor(distance: number): string {
  if (distance < 0.3) return "text-success";
  if (distance < 0.6) return "text-warning";
  return "text-destructive";
}

function distanceLabel(distance: number): string {
  if (distance < 0.3) return "High";
  if (distance < 0.6) return "Medium";
  return "Low";
}

export default function KnowledgeSearch() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["knowledge-search", submittedQuery],
    queryFn: () => searchKnowledge(submittedQuery!),
    enabled: !!submittedQuery,
  });

  const { data: stats } = useQuery({
    queryKey: ["knowledge-stats"],
    queryFn: getKnowledgeStats,
  });

  const handleUploadSuccess = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["knowledge-stats"] });
  }, [queryClient]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSubmittedQuery(query.trim());
  }

  const results = data?.results ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
        <p className="text-muted-foreground">Search the indexed literature and papers.</p>
      </div>

      {/* Stats Banner */}
      {stats && (
        <div data-testid="stats-banner" className="flex gap-4">
          <Card className="flex-1">
            <CardContent className="p-3 flex items-center gap-3">
              <FileText className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Documents</p>
                <p className="text-lg font-semibold" data-testid="stat-documents">{stats.total_documents}</p>
              </div>
            </CardContent>
          </Card>
          <Card className="flex-1">
            <CardContent className="p-3 flex items-center gap-3">
              <Layers className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Chunks</p>
                <p className="text-lg font-semibold" data-testid="stat-chunks">{stats.total_chunks}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <UploadZone onUploadSuccess={handleUploadSuccess} />

      <form onSubmit={handleSubmit} className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search papers, methods, findings..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
        />
      </form>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : isError ? (
        <ErrorCard message="Search failed. Please try again." testId="knowledge-search-error" />
      ) : submittedQuery && results.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No results found"
          message={`No matches for "${submittedQuery}".`}
          testId="knowledge-search-empty"
        />
      ) : results.length > 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {results.length} result{results.length !== 1 ? "s" : ""} for "{submittedQuery}"
          </p>
          {results.map((result) => (
            <Card key={result.id}>
              <CardContent className="p-4">
                <p className="text-sm whitespace-pre-wrap line-clamp-4">{result.text}</p>
                <div className="flex items-center flex-wrap gap-2 mt-3">
                  {result.metadata.source && (
                    <Badge variant="outline" className="text-xs">
                      {result.metadata.source}
                    </Badge>
                  )}
                  {result.metadata.year && (
                    <Badge variant="outline" className="text-xs">
                      {result.metadata.year}
                    </Badge>
                  )}
                  {result.metadata.authors && (
                    <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                      {result.metadata.authors}
                    </span>
                  )}
                  <span className={cn("text-xs font-medium ml-auto", distanceColor(result.distance))}>
                    Relevance: {distanceLabel(result.distance)} ({result.distance.toFixed(3)})
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  );
}
