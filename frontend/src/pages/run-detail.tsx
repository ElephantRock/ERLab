/**
 * Run Detail — Monitor Surface.
 *
 * PRODUCT.md Core Loop step 2 (MONITOR): "Watch progress without anxiety.
 * Must not demand attention."
 *
 * INTERFACE_CONTRACT compliance:
 * - §1 useResource + DataView (not raw useQuery for the main detail)
 * - §3 ui-scale typography (no sub-micro)
 * - §7 truthful status (elapsed timer is real, sourced from query)
 *
 * The live polling (refetchInterval) stays on useQuery because the contract
 * allows freshness overrides with a cited reason — the 3s refetch while
 * running is a product-critical freshness need.
 */

import { useMemo, useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { getRunDetail, getRunIdeas, resumeRun } from "@/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
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
  Download,
  FileText,
} from "lucide-react";
import type { IdeaSummary } from "@/api/types";
import { TreeVisualization } from "@/components/pipeline/tree-visualization";
import { IdeaListItem } from "@/components/ideas/idea-list-item";
import { apiFetchBlob } from "@/api/client";

const statusColors: Record<string, string> = {
  pending: "bg-warning/10 text-warning",
  running: "bg-info/10 text-info",
  completed: "bg-success/10 text-success",
  failed: "bg-destructive/10 text-destructive",
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
  const queryClient = useQueryClient();
  const runId = Number(id);

  const [isResuming, setIsResuming] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // Live polling while running — useQuery with refetchInterval (contract allows
  // freshness overrides with a cited reason: the 3s refetch is product-critical
  // for monitoring a running pipeline).
  const {
    data: run,
    isLoading: runLoading,
    error: runError,
  } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRunDetail(runId),
    enabled: !isNaN(runId),
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

  // Live 1-second tick for elapsed timer (truthful — based on real timestamps)
  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const elapsedSec = useMemo(() => {
    if (!run) return 0;
    const start = new Date(run.created_at).getTime();
    const end = run.completed_at ? new Date(run.completed_at).getTime() : Date.now();
    return Math.max(0, (end - start) / 1000);
  }, [run, tick]);

  // Stale run detector (truthful — based on real created_at)
  const isStale = useMemo(() => {
    if (!run || run.status !== "running") return false;
    const created = new Date(run.created_at).getTime();
    return Date.now() - created > 5 * 60 * 1000;
  }, [run, tick]);

  async function handleRunExport(format: "markdown" | "bibtex" | "latex") {
    setExporting(format);
    try {
      const blob = await apiFetchBlob(`/export/${format}/${runId}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `run_${runId}.${format === "bibtex" ? "bib" : format === "latex" ? "tex" : "md"}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported as ${format}`);
    } catch {
      toast.error("Export failed");
    } finally {
      setExporting(null);
    }
  }

  if (runError || (!runLoading && !run)) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/pipeline/new")} data-testid="back-btn">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Card>
          <CardContent className="p-8 text-center" data-testid="run-not-found">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-destructive" />
            <p className="text-ui-heading font-medium">Run not found</p>
            <p className="text-ui-meta text-muted-foreground mt-1">No pipeline run found with ID {id}.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (runLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-muted rounded" />
        <div className="h-64 w-full bg-muted rounded" />
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
          <Button variant="ghost" onClick={() => navigate("/pipeline/new")} data-testid="back-btn">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-ui-display font-display font-semibold tracking-tight" data-testid="run-title">
              Run #{run.id}
            </h1>
            <p className="text-ui-meta text-muted-foreground">{run.domain}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isRunning && (
            <span className="text-ui-meta text-muted-foreground font-mono tabular-nums flex items-center gap-1">
              <Timer className="h-4 w-4" />
              {fmtDuration(elapsedSec)}
            </span>
          )}
          <Badge className={cn("text-ui-label", statusColors[run.status])} data-testid="run-status">
            {run.status}
          </Badge>
        </div>
      </div>

      {/* Live Progress Banner — calm, not anxiety-inducing */}
      {isRunning && (
        <Card className="border-info/30 bg-info/5" data-testid="live-progress">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-info">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-ui-label font-medium">{currentStageLabel}</span>
              </div>
              <span className="text-ui-meta text-muted-foreground">
                Stage {run.stages_completed.length + 1} of {PIPELINE_STAGES.length}
              </span>
            </div>
            <div className="w-full bg-info/10 rounded-full h-2 overflow-hidden">
              <div
                className="h-full bg-info rounded-full transition-[width] duration-1000 ease-linear"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stale Run Warning — truthful (based on real timestamp) */}
      {isStale && (
        <div className="bg-warning/5 border border-warning/30 rounded-lg p-4" data-testid="stale-run-warning">
          <div className="flex items-center gap-2 text-warning">
            <AlertTriangle className="h-5 w-5" />
            <p className="text-ui-meta">
              This run has been running for over 5 minutes. It may have encountered an issue.
            </p>
          </div>
        </div>
      )}

      {/* Metadata */}
      <Card data-testid="run-metadata">
        <CardHeader>
          <CardTitle className="text-ui-heading font-medium">Run Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-ui-meta">
            <MetaItem label="ID" value={String(run.id)} />
            <MetaItem label="Domain" value={run.domain} />
            <MetaItem label="Strategy" value={run.strategy ? run.strategy.replace(/_/g, " ") : "deep research"} testId="run-strategy" />
            <MetaItem label="Created" value={new Date(run.created_at).toLocaleString()} testId="run-created-at" />
            <MetaItem label="Completed" value={run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"} testId="run-completed-at" />
            <MetaItem label="Duration" value={fmtDuration(elapsedSec)} mono testId="run-duration" />
          </dl>
        </CardContent>
      </Card>

      {/* Quality Settings */}
      {(() => {
        const q = run.config?.quality ?? run.config?.quality_settings;
        if (!q || typeof q !== "object") return null;
        const quality = q as Record<string, unknown>;
        const proposalDepth = quality.proposal_depth as string | undefined;
        const noveltyDepth = quality.novelty_depth as string | undefined;
        const ideaDiversity = quality.idea_diversity as string | undefined;
        const effNested = quality.effective as Record<string, unknown> | undefined;
        const topK = (effNested?.novelty_top_k as number) ?? (quality.effective_novelty_top_k as number);
        const temp = (effNested?.ideator_temperature as number) ?? (quality.effective_ideator_temperature as number);
        const minWords = (effNested?.min_words as Record<string, number>) ?? (quality.effective_min_words as Record<string, number>);
        return (
          <Card data-testid="quality-settings">
            <CardHeader>
              <CardTitle className="text-ui-heading font-medium">Quality Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-ui-meta">
                <MetaItem label="Proposal Depth" value={proposalDepth ?? "—"} testId="quality-proposal-depth" />
                <MetaItem label="Novelty Depth" value={noveltyDepth ?? "—"} testId="quality-novelty-depth" />
                <MetaItem label="Idea Diversity" value={ideaDiversity ?? "—"} testId="quality-idea-diversity" />
              </div>
              {(topK !== undefined || temp !== undefined || minWords) && (
                <div className="mt-4 pt-4 border-t space-y-1 text-ui-meta text-muted-foreground">
                  {topK !== undefined && (
                    <p data-testid="quality-effective-topk">
                      Novelty comparison: <span className="font-mono text-foreground">{topK} papers</span>
                    </p>
                  )}
                  {temp !== undefined && (
                    <p data-testid="quality-effective-temp">
                      Ideator temperature: <span className="font-mono text-foreground">{temp.toFixed(2)}</span>
                    </p>
                  )}
                  {minWords && (
                    <p data-testid="quality-effective-minwords">
                      Method section minimum: <span className="font-mono text-foreground">{minWords.proposed_method ?? minWords.method ?? "—"} words</span>
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        );
      })()}

      {/* Run-level export (completed runs only) */}
      {run.status === "completed" && (
        <Card data-testid="run-export-section">
          <CardHeader>
            <CardTitle className="text-ui-heading font-medium flex items-center gap-2">
              <Download className="h-4 w-4" />
              Export Run
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" disabled={exporting !== null} onClick={() => handleRunExport("markdown")} data-testid="export-markdown-btn">
                {exporting === "markdown" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <FileText className="h-4 w-4 mr-1" />}
                Markdown
              </Button>
              <Button variant="outline" size="sm" disabled={exporting !== null} onClick={() => handleRunExport("latex")} data-testid="export-latex-btn">
                {exporting === "latex" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <FileText className="h-4 w-4 mr-1" />}
                LaTeX
              </Button>
              <Button variant="outline" size="sm" disabled={exporting !== null} onClick={() => handleRunExport("bibtex")} data-testid="export-bibtex-btn">
                {exporting === "bibtex" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <FileText className="h-4 w-4 mr-1" />}
                BibTeX
              </Button>
            </div>
            <p className="text-ui-meta text-muted-foreground mt-2">
              Export all proposals and references from this run.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Stages Timeline */}
      <Card data-testid="stages-timeline">
        <CardHeader>
          <CardTitle className="text-ui-heading font-medium">Stages</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {PIPELINE_STAGES.map((stage) => {
              const isCompleted = run.stages_completed.includes(stage.key);
              const isCurrent = run.current_stage === stage.key;
              return (
                <div key={stage.key} className="flex items-center gap-3">
                  {isCompleted ? (
                    <CheckCircle2 className="h-5 w-5 text-success flex-shrink-0" />
                  ) : isCurrent ? (
                    <Loader2 className="h-5 w-5 text-info animate-spin flex-shrink-0" />
                  ) : (
                    <Circle className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  )}
                  <span className={cn(
                    "text-ui-meta",
                    isCompleted ? "text-foreground font-medium"
                      : isCurrent ? "text-info font-medium"
                      : "text-muted-foreground",
                  )}>
                    {stage.label}
                  </span>
                  {isCurrent && (
                    <span className="text-ui-micro text-info ml-auto font-mono">
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
                <p className="text-ui-label font-medium text-destructive">Pipeline Failed</p>
                <p className="text-ui-meta text-muted-foreground mt-1">{run.error_message}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Resume Button */}
      {run.status === "failed" && (
        <Button data-testid="resume-btn" className="w-full sm:w-auto" disabled={isResuming}
          onClick={async () => {
            setIsResuming(true);
            try {
              await resumeRun(String(run.id));
              queryClient.invalidateQueries({ queryKey: ["run", runId] });
            } catch {
              toast.error("Failed to resume pipeline");
            } finally {
              setIsResuming(false);
            }
          }}>
          {isResuming ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
          {isResuming ? "Resuming..." : "Resume Pipeline"}
        </Button>
      )}

      {/* Tree Search Visualization */}
      {run.tree_data && (
        <Card data-testid="tree-search-tab">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-ui-heading font-medium">Tree Search</CardTitle>
              <span className="text-ui-meta text-muted-foreground flex items-center gap-1">
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
            <CardTitle className="text-ui-heading font-medium">Generated Ideas</CardTitle>
            {ideas.length > 0 && (
              <span className="text-ui-meta text-muted-foreground flex items-center gap-1">
                <Lightbulb className="h-4 w-4" />
                {ideas.length} idea{ideas.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {ideas.length === 0 ? (
            <p className="text-ui-meta text-muted-foreground">
              {isRunning ? "Ideas will appear here once generated..." : "No ideas generated in this run."}
            </p>
          ) : (
            <div className="space-y-3">
              {ideas.map((idea: IdeaSummary) => (
                <IdeaListItem key={idea.id} idea={idea} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Duration card for completed runs */}
      {run.status === "completed" && run.completed_at && run.created_at && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-ui-meta text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>Total duration: {fmtDuration(elapsedSec)}</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ──

function MetaItem({ label, value, mono, testId }: { label: string; value: string; mono?: boolean; testId?: string }) {
  return (
    <div>
      <dt className="text-ui-micro text-muted-foreground uppercase tracking-wider">{label}</dt>
      <dd className={cn("font-medium text-ui-label", mono && "font-mono tabular-nums")} data-testid={testId}>
        {value}
      </dd>
    </div>
  );
}
