/**
 * RevisionHistoryDrawer — Shows revision history for a proposal section.
 *
 * Displays chronological list of revisions with quality snapshots.
 * Each non-current revision has a "Restore this version" button.
 * Shows synthetic original entry when no prior revisions exist.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  History,
  RotateCcw,
  CheckCircle2,
  Loader2,
  GitCommit,
  Clock,
} from "lucide-react";
import { getSectionRevisions, restoreSection } from "@/api/ideas";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export function RevisionHistoryDrawer({
  ideaId,
  sectionKey,
  sectionLabel,
  currentHash,
}: {
  ideaId: number;
  sectionKey: string;
  sectionLabel: string;
  currentHash: string;
}) {
  const queryClient = useQueryClient();
  const [restoringId, setRestoringId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["section-revisions", ideaId, sectionKey],
    queryFn: () => getSectionRevisions(ideaId, sectionKey),
  });

  const restoreMutation = useMutation({
    mutationFn: (revisionId: number) =>
      restoreSection(ideaId, sectionKey, revisionId, currentHash),
    onMutate: (revisionId) => setRestoringId(revisionId),
    onSuccess: () => {
      toast.success("Section restored to previous version");
      queryClient.invalidateQueries({ queryKey: ["section-revisions", ideaId, sectionKey] });
      queryClient.invalidateQueries({ queryKey: ["idea", ideaId] });
    },
    onError: (err: Error) => {
      toast.error("Restore failed", { description: err.message });
    },
    onSettled: () => setRestoringId(null),
  });

  return (
    <Card data-testid={`revision-drawer-${sectionKey}`}>
      <CardHeader>
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <History className="h-4 w-4" />
          Revision History — {sectionLabel}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading revisions...
          </div>
        )}

        {data && data.revisions.length === 0 && !data.synthetic_original && (
          <p className="text-sm text-muted-foreground">No revision history available.</p>
        )}

        {/* Synthetic original entry */}
        {data?.synthetic_original && (
          <div
            className="rounded-lg border border-muted bg-muted/30 p-3"
            data-testid="revision-synthetic-original"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-3 w-3 text-muted-foreground" />
                <span className="text-sm font-medium">Original (pipeline)</span>
              </div>
              {data.synthetic_original.section_hash === currentHash && (
                <Badge variant="outline" className="text-xs text-success border-success/30">
                  Current
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {data.synthetic_original.note}
            </p>
            {data.synthetic_original.quality_summary && (
              <QualityBadge qc={data.synthetic_original.quality_summary} />
            )}
          </div>
        )}

        {/* Revision entries */}
        {data?.revisions.map((rev) => (
          <div
            key={rev.id}
            className={cn(
              "rounded-lg border p-3",
              rev.is_current
                ? "border-success/30 bg-success/5"
                : "border-muted",
            )}
            data-testid={`revision-entry-${rev.id}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitCommit className="h-3 w-3 text-muted-foreground" />
                <span className="text-sm font-medium">
                  Revision #{rev.id}
                </span>
                <Badge variant="outline" className="text-xs capitalize">
                  {rev.source}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(rev.created_at).toLocaleString()}
                </span>
              </div>
              {rev.is_current && (
                <Badge variant="outline" className="text-xs text-success border-success/30">
                  <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
                  Current
                </Badge>
              )}
            </div>

            {/* Quality snapshot */}
            {rev.quality_summary && (
              <QualityBadge qc={rev.quality_summary} />
            )}

            {/* Model receipt */}
            {rev.model_receipt && (
              <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-mono">
                  {(rev.model_receipt as Record<string, string>).served_model}
                </span>
                <span>via {(rev.model_receipt as Record<string, string>).provider}</span>
              </div>
            )}

            {/* Restore button for non-current */}
            {!rev.is_current && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => restoreMutation.mutate(rev.id)}
                disabled={restoringId === rev.id}
                data-testid={`restore-button-${rev.id}`}
              >
                {restoringId === rev.id ? (
                  <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
                ) : (
                  <RotateCcw className="mr-1.5 h-3 w-3" />
                )}
                Restore this version
              </Button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function QualityBadge({
  qc,
}: {
  qc: {
    passed: boolean;
    word_count: number;
    min_words: number;
    failures: string[];
  };
}) {
  return (
    <div className="mt-1.5 flex items-center gap-2 text-xs">
      {qc.passed ? (
        <span className="text-success flex items-center gap-1">
          <CheckCircle2 className="h-2.5 w-2.5" />
          All checks passed
        </span>
      ) : (
        <span className="text-warning">
          {qc.failures.length} issue{qc.failures.length !== 1 ? "s" : ""}
        </span>
      )}
      <span className="text-muted-foreground font-mono">
        {qc.word_count}/{qc.min_words} words
      </span>
    </div>
  );
}
