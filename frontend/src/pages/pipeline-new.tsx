/**
 * Pipeline New — Direct Surface.
 *
 * PRODUCT.md Core Loop step 1 (DIRECT): "Launch a run on a domain, choose
 * a strategy. Should take < 1 minute."
 *
 * INTERFACE_CONTRACT compliance:
 * - §3 ui-scale typography (no sub-micro, no telemetry headings)
 * - §7 truthful status — "System ready" pulsing dot removed, "Local GPU"
 *   hardcoded label replaced with real config value or "—"
 *
 * Preserves all existing functionality: config form, autonomous cycle,
 * pipeline preview, SSE progress, cancel, results, run-another.
 */

import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import { AutonomousForm } from "@/components/pipeline/autonomous-form";
import { StageProgress } from "@/components/pipeline/stage-progress";
import { usePipelineProgress } from "@/hooks/usePipelineProgress";
import { useSession } from "@/hooks/useSession";
import { triggerRun, getRunIdeas, cancelRun, getEstimate } from "@/api/pipeline";
import { listExperimentSpecs } from "@/api/experiments";
import { getSystemStatus } from "@/api/status";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ErrorCard } from "@/components/ui/error-card";
import { IdeaListItem } from "@/components/ideas/idea-list-item";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { PipelineRunRequest, IdeaSummary } from "@/api/types";
import {
  CheckCircle2, Lightbulb, AlertCircle, XCircle, ExternalLink,
  Search, FileText, GitBranch, FilePen,
  Activity, Download, Clock, ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useResource } from "@/lib/useResource";
import { DataView } from "@/components/ui/data-view";

// ── Strategy-aware pipeline preview ──
// The backend estimate is derived from pipeline.yaml, so the preview follows
// the selected runtime strategy instead of showing one static six-step story.
const PIPELINE_BANDS = [
  { key: "literature", icon: Search, label: "Literature", sub: "Search & ingest", stages: ["literature_search", "ingestion", "trimmer"] },
  { key: "gaps", icon: GitBranch, label: "Gaps", sub: "Analyze & reflect", stages: ["gap_analysis", "gap_reflection"] },
  { key: "ideas", icon: Lightbulb, label: "Ideas", sub: "Generate & score", stages: ["idea_generation", "idea_reflection", "novelty_checking", "feasibility_scoring", "mechanical_metrics"] },
  { key: "proposal", icon: FilePen, label: "Proposal", sub: "Synthesize & review", stages: ["proposal_synthesis", "adversarial_review", "evaluation"] },
  { key: "experiment", icon: Activity, label: "Experiment", sub: "Execute registered spec", stages: ["experiment_execution"] },
  { key: "paper", icon: FileText, label: "Paper", sub: "Synthesize & audit", stages: ["paper_synthesis", "citation_audit", "proposal_deepening"] },
  { key: "export", icon: Download, label: "Finalize", sub: "Persist / export", stages: ["export"] },
] as const;

function buildPipelineFlow(stageNames: string[]) {
  const enabled = new Set(stageNames);
  return PIPELINE_BANDS.filter((band) => band.stages.some((stage) => enabled.has(stage)));
}

const STRATEGY_OUTPUTS: Record<string, Array<{ icon: React.ElementType; label: string; value: string }>> = {
  fast_scan: [
    { icon: FileText, label: "Discovered papers", value: "Up to 50" },
    { icon: GitBranch, label: "Research gaps", value: "Configured limit" },
    { icon: Lightbulb, label: "Generated ideas", value: "Enabled" },
    { icon: FilePen, label: "Concise proposals", value: "Per idea" },
  ],
  deep_research: [
    { icon: FileText, label: "Discovered papers", value: "Up to 50" },
    { icon: GitBranch, label: "Research gaps", value: "Configured limit" },
    { icon: Lightbulb, label: "Generated ideas", value: "Enabled" },
    { icon: FilePen, label: "Full proposals", value: "Per idea" },
    { icon: FileText, label: "Full research papers", value: "Per proposal" },
  ],
  academic_proposal: [
    { icon: FileText, label: "Discovered papers", value: "Up to 50" },
    { icon: GitBranch, label: "Research gaps", value: "Configured limit" },
    { icon: Lightbulb, label: "Generated ideas", value: "Enabled" },
    { icon: FilePen, label: "Full proposals", value: "Per idea" },
    { icon: FileText, label: "Full research papers", value: "Per proposal" },
  ],
  literature_review: [
    { icon: FileText, label: "Discovered papers", value: "Up to 50" },
    { icon: GitBranch, label: "Research gaps", value: "Configured limit" },
  ],
};

export default function PipelineNew() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialTopic = searchParams.get("topic") || "";
  const [runId, setRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<IdeaSummary[]>([]);
  const [ideasError, setIdeasError] = useState<string | null>(null);
  const [ideasLoading, setIdeasLoading] = useState(false);
  const [activeStrategy, setActiveStrategy] = useState("fast_scan");
  const [activeExperimentSpecId, setActiveExperimentSpecId] = useState<string | null>(null);
  const { sessionId } = useSession();
  const { stages, isComplete, isConnected } = usePipelineProgress(runId);

  const [isCancelling, setIsCancelling] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const isRunning = !!runId && !isComplete && isConnected && !isCancelled;
  const completedStages = stages.filter((s) => s.status === "completed");
  const hasPartialResults = isCancelled && completedStages.length > 0;

  // ── System status (truthful — from real query, not hardcoded) ──
  const systemStatusResource = useResource(["system-status"], () => getSystemStatus(), { staleTime: 30000 });

  // ── Registered experiment catalog (read-only backend registry) ──
  const experimentCatalogResource = useResource(
    ["experiment-specs"],
    () => listExperimentSpecs(),
    { staleTime: 60000, isEmpty: () => false },
  );
  const experimentCatalog = experimentCatalogResource.status === "ready" ? experimentCatalogResource.data : null;

  // ── Estimate (real, from backend) ──
  // The backend adds experiment_execution only when a registered spec is selected.
  const estimateResource = useResource(
    ["estimate", activeStrategy, activeExperimentSpecId],
    () => getEstimate(activeStrategy, activeExperimentSpecId),
    { staleTime: 60000 },
  );
  const estimate = estimateResource.status === "ready" ? estimateResource.data : null;
  const previewFlow = estimate ? buildPipelineFlow((estimate.breakdown ?? []).map((stage) => stage.stage)) : [];
  const baseExpectedOutputs = STRATEGY_OUTPUTS[activeStrategy] ?? STRATEGY_OUTPUTS.deep_research ?? [];
  const expectedOutputs = activeExperimentSpecId
    ? [...baseExpectedOutputs, { icon: Activity, label: "Registered experiment", value: activeExperimentSpecId }]
    : baseExpectedOutputs;

  async function handleStart(config: PipelineRunRequest) {
    setIsLoading(true);
    setError(null);
    setIdeas([]);
    setIdeasError(null);
    try {
      const configWithSession = { ...config, session_id: sessionId || undefined };
      const res = await triggerRun(configWithSession);
      setRunId(res.run_id);
    } catch {
      setError("Failed to start pipeline");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!isComplete || !runId) return;
    // Capture runId into a const so the nested async closure sees a
    // fixed `string` rather than the reopened `string | null` (TS does
    // not preserve the outer narrowing inside function closures).
    const activeRunId = runId;
    async function fetchIdeas() {
      setIdeasLoading(true);
      setIdeasError(null);
      try {
        const ideasData = await getRunIdeas(activeRunId);
        setIdeas(ideasData.ideas);
      } catch {
        setIdeas([]);
        setIdeasError("Failed to load results");
      } finally {
        setIdeasLoading(false);
      }
    }
    fetchIdeas();
  }, [isComplete, runId]);

  function handleCancelClick() { setCancelError(null); setShowCancelConfirm(true); }
  function handleCancelDismiss() { setShowCancelConfirm(false); }
  async function handleCancelConfirm() {
    if (!runId) return;
    setIsCancelling(true);
    setCancelError(null);
    try {
      await cancelRun(runId);
      setIsCancelled(true);
      setShowCancelConfirm(false);
    } catch {
      setCancelError("Failed to cancel run");
    } finally {
      setIsCancelling(false);
    }
  }
  function handleReset() {
    setRunId(null); setIdeas([]); setIdeasError(null); setError(null);
    setIsCancelled(false); setCancelError(null); setShowCancelConfirm(false);
  }

  return (
    <div className="space-y-6 animate-fade-in" data-testid="pipeline-new-page">
      {/* ── Header ── */}
      <div>
        <h1 className="text-ui-display font-display font-semibold tracking-tight">New Run</h1>
        <p className="text-ui-meta text-muted-foreground">Configure and launch a research pipeline.</p>
      </div>

      {/* ══ PRE-RUN STATE: Config + Sidebar ══ */}
      {!runId && (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* LEFT: Config Form */}
          <div className="lg:col-span-2">
            <Tabs defaultValue="single">
              <TabsList>
                <TabsTrigger value="single">Single Run</TabsTrigger>
                <TabsTrigger value="autonomous">Autonomous Cycle</TabsTrigger>
              </TabsList>
              <TabsContent value="single">
                <RunConfigForm
                  onSubmit={handleStart}
                  isLoading={isLoading}
                  initialDomain={initialTopic}
                  onStrategyChange={setActiveStrategy}
                  experimentCatalog={experimentCatalog}
                  experimentCatalogLoading={experimentCatalogResource.status === "loading"}
                  experimentCatalogError={experimentCatalogResource.status === "error"}
                  onExperimentSpecChange={setActiveExperimentSpecId}
                />
              </TabsContent>
              <TabsContent value="autonomous">
                <AutonomousForm onCycleStarted={setRunId} />
              </TabsContent>
            </Tabs>
          </div>

          {/* RIGHT: Pipeline Preview + System Info */}
          <div className="lg:col-span-1">
            <div className="sticky top-6 space-y-4">
              {/* Pipeline Flow Preview */}
              <Card className="card-shadow">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-border/50">
                    <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
                      Pipeline Flow
                    </span>
                    {estimate && (
                      <span className="flex items-center gap-1 text-ui-micro text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {estimate.estimated_time_display}
                      </span>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    {previewFlow.length > 0 ? previewFlow.map((stage) => (
                      <div key={stage.key} className="flex items-center gap-2">
                        <div className="h-7 w-7 rounded-lg bg-muted/40 flex items-center justify-center">
                          <stage.icon className="h-3.5 w-3.5 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="text-ui-meta font-medium leading-tight">{stage.label}</p>
                          <p className="text-ui-micro text-muted-foreground leading-tight">{stage.sub}</p>
                        </div>
                      </div>
                    )) : (
                      <p className="text-ui-micro text-muted-foreground">Loading strategy plan...</p>
                    )}
                  </div>
                  {/* Cost — truthful from real estimate */}
                  {estimate && (
                    <div className="flex items-center justify-between pt-2 border-t border-border/50">
                      <span className="text-ui-micro text-muted-foreground">ESTIMATED COST</span>
                      <div className="flex items-center gap-2">
                        <span className="text-ui-label font-semibold">{estimate.cost_display}</span>
                        {estimate.local_cost_usd === 0 && (
                          <Badge variant="outline" className="text-ui-micro py-0 px-1 text-success border-success/20 bg-success/5">
                            Local
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* System Info — §7 truthful: no hardcoded "System ready", no "Local GPU" */}
              <Card className="card-shadow">
                <CardContent className="p-4 space-y-3">
                  <div className="pb-2 border-b border-border/50">
                    <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
                      System Status
                    </span>
                  </div>
                  <DataView resource={systemStatusResource} testId="sys-status" loading={{ lines: 3 }}>
                    {(status) => (
                      <div className="space-y-2">
                        <SystemRow label="Provider" value={String(status.config?.default_provider ?? "—")} />
                        <SystemRow label="Governance" value={status.config?.governance_enabled ? "Enabled" : "Disabled"} />
                        <SystemRow label="Memory" value={status.config?.memory_enabled ? "Enabled" : "Disabled"} />
                      </div>
                    )}
                  </DataView>
                  {/* NO "System ready" pulsing dot. §7: if unverified, says nothing. */}
                </CardContent>
              </Card>

              {/* Expected Outputs */}
              <Card className="card-shadow">
                <CardContent className="p-4 space-y-2">
                  <div className="pb-2 border-b border-border/50">
                    <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">
                      Expected Outputs
                    </span>
                  </div>
                  <div className="space-y-1.5 text-ui-meta">
                    {expectedOutputs.map((output) => (
                      <OutputRow key={output.label} icon={output.icon} label={output.label} value={output.value} />
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* ── Error ── */}
      {error && <ErrorCard message={error} testId="trigger-error" />}

      {/* ══ RUNNING / COMPLETE STATE ══ */}
      {runId && (
        <Card className="card-shadow">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                {isComplete ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : isRunning ? (
                  <Activity className="h-5 w-5 text-accent animate-pulse" />
                ) : (
                  <Clock className="h-5 w-5 text-muted-foreground" />
                )}
                Pipeline Progress
              </CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono">Run #{runId}</Badge>
                {isCancelled ? (
                  <Badge variant="destructive" data-testid="cancelled-badge">Cancelled</Badge>
                ) : isComplete ? (
                  <Badge className="bg-success/10 text-success">Complete</Badge>
                ) : isConnected ? (
                  <Badge className="bg-accent/10 text-accent" data-testid="live-badge">Live</Badge>
                ) : (
                  <Badge variant="secondary">Connecting...</Badge>
                )}
                {isRunning && (
                  <Button variant="destructive" size="sm" onClick={handleCancelClick} disabled={isCancelling} data-testid="cancel-run-btn">
                    {isCancelling ? "Cancelling..." : "Cancel Run"}
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Visual stage flow — ui-micro floor, no text-[8px]/[9px] */}
            <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-2">
              {stages.map((stage, i) => (
                <div key={stage.key} className="flex items-center gap-1 flex-shrink-0">
                  <div className={cn(
                    "flex flex-col items-center gap-1 px-2 py-1.5 rounded-lg transition-all min-w-[80px]",
                    stage.status === "completed" && "bg-success/5",
                    stage.status === "running" && "bg-accent/5",
                  )}>
                    <div className={cn(
                      "h-6 w-6 rounded-full flex items-center justify-center text-ui-micro font-mono font-bold transition-all",
                      stage.status === "completed" ? "bg-success/15 text-success"
                        : stage.status === "running" ? "bg-accent/15 text-accent animate-pulse"
                        : "bg-muted text-muted-foreground",
                    )}>
                      {stage.status === "completed" ? "✓" : i + 1}
                    </div>
                    <span className={cn(
                      "text-ui-micro font-medium leading-tight text-center max-w-[72px] truncate",
                      stage.status === "completed" ? "text-success"
                        : stage.status === "running" ? "text-accent"
                        : "text-muted-foreground",
                    )}>
                      {stage.label}
                    </span>
                    {stage.elapsed > 0 && (
                      <span className="text-ui-micro text-muted-foreground font-mono">
                        {stage.elapsed.toFixed(0)}s
                      </span>
                    )}
                  </div>
                  {i < stages.length - 1 && (
                    <div className={cn(
                      "h-0.5 w-3 rounded transition-colors",
                      stage.status === "completed" ? "bg-success/30" : "bg-border",
                    )} />
                  )}
                </div>
              ))}
            </div>

            <StageProgress stages={stages} currentStage={null} />
          </CardContent>

          {/* Cancel confirmation dialog */}
          <Dialog open={showCancelConfirm} onOpenChange={(open) => { if (!open) handleCancelDismiss(); }}>
            <DialogContent className="max-w-md" data-testid="cancel-confirm-dialog">
              <div className="flex items-center gap-2 mb-3">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <h2 className="text-ui-heading font-semibold">Cancel Pipeline Run?</h2>
              </div>
              <p className="text-ui-meta text-muted-foreground mb-4">
                This will abort the running pipeline. Completed stages will be preserved, but no further stages will execute.
              </p>
              {cancelError && <p className="text-ui-meta text-destructive mb-4" data-testid="cancel-error">{cancelError}</p>}
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleCancelDismiss} data-testid="cancel-dismiss-btn">No, Continue</Button>
                <Button variant="destructive" onClick={handleCancelConfirm} disabled={isCancelling} data-testid="cancel-confirm-btn">
                  {isCancelling ? "Cancelling..." : "Yes, Cancel Run"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>

          {isComplete && (
            <CardContent className="border-t pt-4">
              <div className="flex items-center gap-2 text-success">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-medium text-ui-label">Pipeline completed successfully</span>
              </div>
            </CardContent>
          )}

          {isCancelled && (
            <CardContent className="border-t pt-4" data-testid="cancelled-partial-results">
              <div className="flex items-center gap-2 text-destructive">
                <XCircle className="h-5 w-5" />
                <span className="font-medium text-ui-label">Pipeline run was cancelled</span>
              </div>
              {hasPartialResults && (
                <p className="text-ui-meta text-muted-foreground mt-1">
                  {completedStages.length} of {stages.length} stage{completedStages.length !== 1 ? "s" : ""} completed before cancellation.
                </p>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {/* ══ Results ══ */}
      {(isComplete || isCancelled) && (
        <div className="space-y-4" data-testid="pipeline-results">
          <Card className="card-shadow">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {isComplete ? (
                    <>
                      <CheckCircle2 className="h-5 w-5 text-success" />
                      <CardTitle>Results</CardTitle>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-5 w-5 text-destructive" />
                      <CardTitle>Partial Results</CardTitle>
                    </>
                  )}
                </div>
                {ideas.length > 0 && (
                  <span className="flex items-center gap-1 text-ui-meta text-muted-foreground">
                    <Lightbulb className="h-4 w-4" />
                    {ideas.length} idea{ideas.length !== 1 ? "s" : ""} generated
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {ideasError && <ErrorCard message={ideasError} testId="ideas-error" />}
              {ideasLoading && <p className="text-ui-meta text-muted-foreground">Loading results...</p>}
              {!ideasLoading && !ideasError && ideas.length === 0 && (
                <p className="text-ui-meta text-muted-foreground">
                  {isCancelled
                    ? "No ideas were generated before cancellation."
                    : activeStrategy === "literature_review"
                      ? "Literature Review does not generate ideas; review the persisted gaps from this run."
                      : "No ideas generated in this run."}
                </p>
              )}
              {!ideasLoading && ideas.length > 0 && (
                <div className="space-y-3">
                  {ideas.map((idea) => (
                    <IdeaListItem key={idea.id} idea={idea} />
                  ))}
                </div>
              )}
              <div className="flex items-center gap-3 mt-4 pt-4 border-t">
                {isComplete && runId && (
                  <Button variant="outline" onClick={() => navigate(`/runs/${runId}`)} data-testid="view-run-detail">
                    <ExternalLink className="h-4 w-4 mr-1" />
                    View Run Details
                  </Button>
                )}
                <Button variant="outline" onClick={() => navigate("/ideas")} data-testid="view-all-ideas">
                  <ArrowRight className="h-4 w-4 mr-1" />
                  View All Ideas
                </Button>
                <Button variant="default" onClick={handleReset} data-testid="run-another">
                  Run Another
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// ── Sub-components (restyled to ui-scale) ──

function SystemRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 text-ui-meta">
      <span className="text-muted-foreground flex-1">{label}</span>
      <span className="font-mono font-medium capitalize">{value}</span>
    </div>
  );
}

function OutputRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3 w-3 text-muted-foreground flex-shrink-0" />
      <span className="text-muted-foreground flex-1">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  );
}
