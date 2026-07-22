import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, BookOpen, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import type { Paper } from "@/api/literature";

export interface PaperCardProps {
  paper: Paper;
  onIngest: (paper: Paper) => void;
  isIngesting?: boolean;
  isIngested?: boolean;
  ingestError?: string;
}

function sourceColor(source: string): string {
  switch (source) {
    case "semantic_scholar":
      return "bg-info/10 text-info";
    case "arxiv":
      return "bg-destructive/10 text-destructive";
    case "openalex":
      return "bg-success/10 text-success";
    default:
      return "bg-muted/50 text-muted-foreground";
  }
}

export function PaperCard({ paper, onIngest, isIngesting, isIngested, ingestError }: PaperCardProps) {
  const [confirming, setConfirming] = useState(false);

  function handleIngestClick() {
    if (isIngesting || isIngested) return;
    if (!confirming) {
      setConfirming(true);
      return;
    }
    onIngest(paper);
    setConfirming(false);
  }

  const authorNames = paper.authors.map((a) => a.name).join(", ");
  const truncatedAbstract =
    paper.abstract && paper.abstract.length > 250
      ? paper.abstract.slice(0, 250) + "…"
      : paper.abstract;

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-sm leading-tight" data-testid="paper-title">
            {paper.title}
          </h3>
          {paper.url && (
            <a
              href={paper.url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>

        {authorNames && (
          <p className="text-xs text-muted-foreground mt-1" data-testid="paper-authors">
            {authorNames}
          </p>
        )}

        {truncatedAbstract && (
          <p className="text-xs text-muted-foreground mt-2 line-clamp-3">
            {truncatedAbstract}
          </p>
        )}

        <div className="flex items-center flex-wrap gap-2 mt-3">
          <Badge variant="outline" className={`text-xs ${sourceColor(paper.source)}`}>
            {paper.source}
          </Badge>
          {paper.year && (
            <Badge variant="outline" className="text-xs" data-testid="paper-year">
              {paper.year}
            </Badge>
          )}
          {paper.citation_count != null && (
            <span className="text-xs text-muted-foreground">
              {paper.citation_count.toLocaleString()} citations
            </span>
          )}
          {paper.doi && (
            <span className="text-xs text-muted-foreground truncate max-w-[180px]">
              DOI: {paper.doi}
            </span>
          )}
        </div>

        <div className="mt-3 flex justify-end items-center gap-2">
          {ingestError && (
            <span className="text-xs text-destructive flex items-center gap-1" data-testid="ingest-error">
              <AlertCircle className="h-3 w-3" />
              {ingestError}
            </span>
          )}
          {isIngested && (
            <span className="text-xs text-success flex items-center gap-1" data-testid="ingested-badge">
              <CheckCircle2 className="h-3 w-3" />
              Ingested
            </span>
          )}
          <Button
            size="sm"
            variant={isIngested ? "secondary" : confirming ? "destructive" : "outline"}
            onClick={handleIngestClick}
            disabled={isIngesting || isIngested}
            data-testid="ingest-button"
          >
            {isIngesting ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Ingesting...
              </>
            ) : isIngested ? (
              <>
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Ingested
              </>
            ) : (
              <>
                <BookOpen className="h-3 w-3 mr-1" />
                {confirming ? "Confirm Ingest" : "Ingest"}
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
