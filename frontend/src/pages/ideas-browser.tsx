import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listIdeas } from "@/api/ideas";
import { IdeaCard } from "@/components/ideas/idea-card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useNavigate } from "react-router-dom";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";

export default function IdeasBrowser() {
  const navigate = useNavigate();
  const [domainFilter, setDomainFilter] = useState("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["ideas", { domain: domainFilter, limit, offset: page * limit }],
    queryFn: () =>
      listIdeas({
        domain: domainFilter || undefined,
        limit,
        offset: page * limit,
      }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Research Ideas</h1>
        <p className="text-muted-foreground">
          Browse generated ideas with novelty and feasibility scores.
        </p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Filter by domain..."
          value={domainFilter}
          onChange={(e) => {
            setDomainFilter(e.target.value);
            setPage(0);
          }}
          className="pl-9"
        />
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : data?.ideas.length ? (
        <>
          <p className="text-sm text-muted-foreground">
            {data.total} idea{data.total !== 1 ? "s" : ""} found
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {data.ideas.map((idea) => (
              <IdeaCard
                key={idea.id}
                idea={idea}
                onClick={() => navigate(`/ideas/${idea.id}`)}
              />
            ))}
          </div>
          {data.total > limit && (
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1} of {Math.ceil(data.total / limit)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={(page + 1) * limit >= data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          <p>No ideas found{domainFilter ? ` for "${domainFilter}"` : ""}.</p>
        </div>
      )}
    </div>
  );
}
