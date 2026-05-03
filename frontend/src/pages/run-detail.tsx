import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { getRunDetail, getRunIdeas } from "@/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PIPELINE_STAGES } from "@/lib/constants";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Loader2,
  AlertTriangle,
  Play,
  Lightbulb,
  Clock,
} from "lucide-react";
import type { PipelineRunDetail, IdeaSummary } from "@/api/types";

const statusColors: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const runId = Number(id);
  const [now, setNow] = useState(Date.now());

  const {
    data: run,
    isLoading: runLoading,
    error: runError,
  } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRunDetail(runId),
    enabled: !isNaN(runId),
  });

  const { data: ideasData } = useQuery({
    queryKey: ["run", runId, "ideas"],
    queryFn: () => getRunIdeas(runId),
    enabled: !isNaN(runId) && !!run,
  });

  // Stale run detector (BATCH-55): re-check every 30 seconds
  const isStale = useMemo(() => {
    if (!run || run.status !== "running") return false;
    const created = new Date(run.created_at).getTime();
    return Date.now() - created > 5 * 60 * 1000; // 5 minutes
  }, [run, now]);

  useEffect(() => {
    if (!run || run.status !== "running") return;
    const interval = setInterval(() => {
      setNow(Date.now());
    }, 30000);
    return () => clearInterval(interval);
  }, [run]);

  if (runError) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/")} data-testid="back-btn">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
        <Card>
          <CardContent className="p-8 text-center" data-testid="run-not-found">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-destructive" />
            <p className="text-lg font-medium">Run not found</p>
            <p className="text-sm text-muted-foreground mt-1">
              No pipeline run found with ID {id}.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (runLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/")} data-testid="back-btn">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </Button>
        <Card>
          <CardContent className="p-8 text-center" data-testid="run-not-found">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-destructive" />
            <p className="text-lg font-medium">Run not found</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const ideas = ideasData?.ideas ?? [];

  return (
    <div className="space-y-6" data-testid="run-detail">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={() => navigate("/")} data-testid="back-btn">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight" data-testid="run-title">
              Run #{run.id}
            </h1>
            <p className="text-sm text-muted-foreground">{run.domain}</p>
          </div>
        </div>
        <Badge className={cn("text-sm", statusColors[run.status])} data-testid="run-status">
          {run.status}
        </Badge>
      </div>

      {/* Stale Run Warning (BATCH-55) */}
      {isStale && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-4" data-testid="stale-run-warning">
          <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
            <AlertTriangle className="h-5 w-5" />
            <p className="text-sm">
              This run has been running for over 5 minutes. It may have encountered an issue.
              You can try refreshing or starting a new run.
            </p>
          </div>
        </div>
      )}

      {/* Metadata */}
      <Card data-testid="run-metadata">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Run Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">ID</dt>
              <dd className="font-medium">{run.id}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Domain</dt>
              <dd className="font-medium">{run.domain}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd className="font-medium" data-testid="run-created-at">
                {new Date(run.created_at).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed</dt>
              <dd className="font-medium" data-testid="run-completed-at">
                {run.completed_at
                  ? new Date(run.completed_at).toLocaleString()
                  : "—"}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Stages Timeline */}
      <Card data-testid="stages-timeline">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Stages</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {PIPELINE_STAGES.map((stage) => {
              const isCompleted = run.stages_completed.includes(stage.key);
              const isCurrent = run.current_stage === stage.key;
              return (
                <div key={stage.key} className="flex items-center gap-3">
                  {isCompleted ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
                  ) : isCurrent ? (
                    <Loader2 className="h-5 w-5 text-blue-600 animate-spin flex-shrink-0" />
                  ) : (
                    <Circle className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  )}
                  <span
                    className={cn(
                      "text-sm",
                      isCompleted ? "text-foreground font-medium" : "text-muted-foreground",
                    )}
                  >
                    {stage.label}
                  </span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Error Message (for failed runs) */}
      {run.status === "failed" && run.error_message && (
        <Card className="border-destructive" data-testid="error-message">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-destructive">Pipeline Failed</p>
                <p className="text-sm text-muted-foreground mt-1">{run.error_message}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Resume Button (for failed runs) */}
      {run.status === "failed" && (
        <Button data-testid="resume-btn" className="w-full sm:w-auto">
          <Play className="h-4 w-4 mr-2" />
          Resume Pipeline
        </Button>
      )}

      {/* Generated Ideas */}
      <Card data-testid="ideas-list">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Generated Ideas</CardTitle>
            {ideas.length > 0 && (
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <Lightbulb className="h-4 w-4" />
                {ideas.length} idea{ideas.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {ideas.length === 0 ? (
            <p className="text-sm text-muted-foreground">No ideas generated in this run.</p>
          ) : (
            <div className="space-y-3">
              {ideas.map((idea: IdeaSummary) => (
                <Card
                  key={idea.id}
                  className="cursor-pointer hover:bg-accent/50 transition-colors"
                  onClick={() => navigate(`/ideas/${idea.id}`)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium line-clamp-1">{idea.title}</p>
                        <p className="text-xs text-muted-foreground">{idea.domain}</p>
                      </div>
                      {idea.overall_score !== null && (
                        <Badge variant="secondary" className="ml-2">
                          {(idea.overall_score * 100).toFixed(0)}%
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Duration info */}
      {run.completed_at && run.created_at && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>
                Duration:{" "}
                {(
                  (new Date(run.completed_at).getTime() -
                    new Date(run.created_at).getTime()) /
                  1000
                ).toFixed(1)}{" "}
                seconds
              </span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
