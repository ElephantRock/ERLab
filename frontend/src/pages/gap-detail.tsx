import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { getGap, listGaps, updateGapStatus } from "@/api/gaps";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, BookOpen, GitBranch, Lightbulb, BarChart3 } from "lucide-react";
import { GapFeedbackForm } from "@/components/gaps/gap-feedback-form";
import type { ResearchGap } from "@/api/types";

/** Gap type badge color mapping. */
const GAP_TYPE_COLORS: Record<string, string> = {
  methodological: "bg-blue-100 text-blue-800",
  empirical: "bg-green-100 text-green-800",
  theoretical: "bg-purple-100 text-purple-800",
  "cross-domain": "bg-orange-100 text-orange-800",
};

export default function GapDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const gapId = Number(id);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["gap", gapId],
    queryFn: () => getGap(gapId),
    enabled: !isNaN(gapId),
  });

  const gap: ResearchGap | undefined = data?.gap;

  // Fetch related ideas (ideas that reference this gap's title)
  const { data: relatedIdeasData } = useQuery({
    queryKey: ["ideas-for-gap", gap?.title],
    queryFn: () =>
      listGaps({ search: gap?.title, limit: 5 } as Record<string, unknown>).catch(() => ({
        gaps: [],
        total: 0,
      })),
    enabled: !!gap?.title,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (isError || !gap) {
    return (
      <div className="space-y-4 text-center py-12">
        <GitBranch className="h-12 w-12 mx-auto text-muted-foreground opacity-50" />
        <h2 className="text-xl font-semibold">Gap not found</h2>
        <p className="text-muted-foreground">
          The research gap with ID {id} could not be found.
        </p>
        <Button variant="outline" onClick={() => navigate("/gaps")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Gaps Explorer
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/gaps")}
          className="mb-2"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Gaps
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">{gap.title}</h1>
        <div className="flex items-center gap-3 mt-2">
          {/* Gap type badge */}
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
              GAP_TYPE_COLORS[gap.gap_type] || "bg-gray-100 text-gray-800"
            }`}
          >
            {gap.gap_type || "unknown"}
          </span>
          {/* Confidence */}
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <div className="w-32 bg-gray-200 rounded-full h-2">
              <div
                className="bg-primary rounded-full h-2 transition-all"
                style={{ width: `${Math.round(gap.confidence * 100)}%` }}
              />
            </div>
            <span className="text-sm text-muted-foreground">
              {Math.round(gap.confidence * 100)}% confidence
            </span>
          </div>
          {/* Status dropdown (BATCH-41) */}
          <select
            value={gap.status || "identified"}
            onChange={async (e) => {
              try { await updateGapStatus(gapId, e.target.value); } catch (err) { toast.error("Failed to update gap status"); } 
            }}
            className="px-2 py-0.5 text-xs border rounded-md bg-background"
            aria-label="Gap lifecycle status"
          >
            <option value="identified">Identified</option>
            <option value="investigating">Investigating</option>
            <option value="addressed">Addressed</option>
          </select>
        </div>
      </div>

      {/* Description */}
      <div className="bg-card border rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-2">Description</h2>
        <p className="text-muted-foreground whitespace-pre-wrap">
          {gap.description || "No description available."}
        </p>
        {gap.potential_impact && (
          <div className="mt-4 pt-4 border-t">
            <h3 className="text-sm font-medium mb-1">Potential Impact</h3>
            <p className="text-sm text-muted-foreground">{gap.potential_impact}</p>
          </div>
        )}
      </div>

      {/* Truth Values */}
      {gap.truth && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            Truth Values
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Frequency</p>
              <p className="text-lg font-medium">{parseFloat(String(gap.truth.frequency)).toFixed(3)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Confidence</p>
              <p className="text-lg font-medium">{parseFloat(String(gap.truth.confidence)).toFixed(3)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Evidence Count</p>
              <p className="text-lg font-medium">{gap.truth.evidence_count}</p>
            </div>
          </div>
        </div>
      )}

      {/* Cluster Membership */}
      {gap.related_clusters && gap.related_clusters.length > 0 && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Cluster Membership
          </h2>
          <div className="flex flex-wrap gap-2">
            {gap.related_clusters.map((clusterId) => (
              <span
                key={clusterId}
                className="px-3 py-1 bg-muted rounded-full text-sm font-medium"
              >
                Cluster {clusterId}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Related Ideas */}
      {gap.idea_count != null && gap.idea_count > 0 && (
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Related Ideas
          </h2>
          <p className="text-sm text-muted-foreground">
            {gap.idea_count} idea{gap.idea_count !== 1 ? "s" : ""} linked to this gap.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => navigate(`/ideas?search=${encodeURIComponent(gap.title)}`)}
          >
            View Related Ideas
          </Button>
        </div>
      )}

      {/* Metadata */}
      <div className="text-xs text-muted-foreground">
        <p>Gap ID: {gap.id}</p>
        {gap.pipeline_run_id && <p>Pipeline Run: {gap.pipeline_run_id}</p>}
      </div>

      {/* Feedback Form (BATCH-41) */}
      <div className="bg-card border rounded-lg p-4">
        <GapFeedbackForm
          gapId={gap.id}
          currentRating={gap.user_rating}
          currentNotes={gap.user_notes}
        />
      </div>
    </div>
  );
}
