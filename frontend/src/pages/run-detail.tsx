import { useMemo, useState, useEffect, useCallback } from "react";
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
  GitBranch,
  Timer,
} from "lucide-react";
import type { IdeaSummary } from "@/api/types";
import { TreeVisualization } from "@/components/pipeline/tree-visualization";

const statusColors: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

function fmtDuration(sec: number): string {
  if (sec < 60) return `${sec.toFixed(0)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m ${s}s`;
}

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const runId = Number(id);

  // Tick every second for live elapsed timer
  const [tick, setTick] = useState(0);

  const {
    data: run,
    isLoading: runLoading,
    error: runError,
  } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRunDetail(runId),
    enabled: !isNaN(runId),
    // Fast refetch while running — every 3 seconds
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && data.status === "running" ? 3000 : false;
    },
  });

  const isRunning = run?.status === "running";

  const { data: ideasData } = useQuery({
    queryKey: ["run", runId, "ideas"],
    queryFn: () => getRunIdeas(runId),
    enabled: !isNaN(runId) && !!run,
    refetchInterval: isRunning ? 5000 : false,
  });

  // Live 1-second tick
  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  // Live elapsed time
  const elapsedSec = useMemo(() => {
    if (!run) return 0;
    const start = new Date(run.created_at).getTime();
    const end = run.completed_at ? new Date(run.completed_at).getTime() : Date.now();
    return Math.max(0, (end - start) / 1000);
  }, [run, tick]);

  // Stale run detector (BATCH-55)
  const isStale = useMemo(() => {
    if (!run || run.status !== "running") return false;
    const created = new Date(run.created_at).getTime();
    return Date.now() - created > 5 * 60 * 1000;
  }, [run, tick]);

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
  const progressPct = Math.min(100, (run.stages_completed.length / PIPELINE_STAGES.length) * 100);
  const currentStageLabel = PIPELINE_STAGES.find((s) => s.key === run.current_stage)?.label ?? run.current_stage;

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
        <div className="flex items-center gap-3">
          {isRunning && (
            <span className="text-sm text-muted-foreground font-mono tabular-nums flex items-center gap-1">
              <Timer className="h-4 w-4" />
              {fmtDuration(elapsedSec)}
            </span>
          )}
          <Badge className={cn("text-sm", statusColors[run.status])} data-testid="run-status">
            {run.status}
          </Badge>
        </div>
      </div>

      {/* Live Progress Banner */}
      {isRunning && (
        <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10" data-testid="live-progress">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-blue-700 dark:text-blue-300">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-sm font-medium">{currentStageLabel}</span>
              </div>
              <span className="text-xs text-muted-foreground">
                Stage {run.stages_completed.length + 1} of {PIPELINE_STAGES.length}
              </span>
            </div>
            <div className="w-full bg-blue-100 dark:bg-blue-900/30 rounded-full h-2 overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-1000 ease-linear"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}

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
              <dt className="text-muted-foreground">Strategy</dt>
              <dd className="font-medium capitalize" data-testid="run-strategy">
                {run.strategy ? run.strategy.replace(/_/g, " ") : "deep research"}
              </dd>
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
                  : "\u2014"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Duration</dt>
              <dd className="font-medium font-mono tabular-nums" data-testid="run-duration">
                {fmtDuration(elapsedSec)}
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
                      isCompleted
                        ? "text-foreground font-medium"
                        : isCurrent
                          ? "text-blue-700 font-medium"
                          : "text-muted-foreground",
                    )}
                  >
                    {stage.label}
                  </span>
                  {isCurrent && (
                    <span className="text-xs text-blue-500 ml-auto font-mono">
                      {fmtDuration(elapsedSec)}
                    </span>
                  )}
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

      {/* Tree Search Visualization (BATCH-63/TASK-02, AC-02-02) */}
      {run.tree_data && (
        <Card data-testid="tree-search-tab">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Tree Search</CardTitle>
              <span className="text-sm text-muted-foreground flex items-center gap-1">
                <GitBranch className="h-4 w-4" />
                {run.tree_data.nodes.length} node{run.tree_data.nodes.length !== 1 ? "s" : ""}
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <TreeVisualization tree_data={run.tree_data} />
          </CardContent>
        </Card>
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
            <p className="text-sm text-muted-foreground">
              {isRunning ? "Ideas will appear here once generated..." : "No ideas generated in this run."}
            </p>
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

      {/* Duration card for completed runs */}
      {run.status === "completed" && run.completed_at && run.created_at && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>Total duration: {fmtDuration(elapsedSec)}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
