import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import { AutonomousForm } from "@/components/pipeline/autonomous-form";
import { StageProgress } from "@/components/pipeline/stage-progress";
import { usePipelineProgress } from "@/hooks/usePipelineProgress";
import { triggerRun, getRunIdeas, cancelRun } from "@/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { PipelineRunRequest, IdeaSummary } from "@/api/types";
import { CheckCircle2, Lightbulb, AlertCircle, XCircle } from "lucide-react";

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
  const [sessionId, setSessionId] = useState<string>("");
  const { stages, isComplete, isConnected } = usePipelineProgress(runId);

  // ── Cancel run state ──────────────────────────────────────────
  const [isCancelling, setIsCancelling] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const isRunning = !!runId && !isComplete && isConnected && !isCancelled;
  const completedStages = stages.filter((s) => s.status === "completed");
  const hasPartialResults = isCancelled && completedStages.length > 0;

  async function handleStart(config: PipelineRunRequest) {
    setIsLoading(true);
    setError(null);
    setIdeas([]);
    setIdeasError(null);
    try {
      const configWithSession = {
        ...config,
        session_id: sessionId || undefined,
      };
      const res = await triggerRun(configWithSession);
      setRunId(res.run_id);
    } catch (err) {
      setError("Failed to start pipeline");
    } finally {
      setIsLoading(false);
    }
  }

  // Fetch ideas when pipeline completes
  useEffect(() => {
    if (!isComplete) return;
    if (!runId) return;

    async function fetchIdeas() {
      setIdeasLoading(true);
      setIdeasError(null);
      try {
        const ideasData = await getRunIdeas(Number(runId));
        setIdeas(ideasData.ideas);
      } catch (err) {
        setIdeas([]);
        setIdeasError("Failed to load results");
      } finally {
        setIdeasLoading(false);
      }
    }

    fetchIdeas();
  }, [isComplete, runId]);

  // ── Cancel handlers (AR-01: explicit user confirmation) ───────
  function handleCancelClick() {
    setCancelError(null);
    setShowCancelConfirm(true);
  }

  function handleCancelDismiss() {
    setShowCancelConfirm(false);
  }

  async function handleCancelConfirm() {
    if (!runId) return;
    setIsCancelling(true);
    setCancelError(null);
    try {
      await cancelRun(runId);
      setIsCancelled(true);
      setShowCancelConfirm(false);
    } catch (err) {
      setCancelError("Failed to cancel run");
    } finally {
      setIsCancelling(false);
    }
  }

  function handleReset() {
    setRunId(null);
    setIdeas([]);
    setIdeasError(null);
    setError(null);
    setIsCancelled(false);
    setCancelError(null);
    setShowCancelConfirm(false);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pipeline</h1>
        <p className="text-muted-foreground">Configure and launch a research pipeline.</p>
      </div>

      {!runId && (
        <>
          <Tabs defaultValue="single">
            <TabsList>
              <TabsTrigger value="single">Single Run</TabsTrigger>
              <TabsTrigger value="autonomous">Autonomous Cycle</TabsTrigger>
            </TabsList>
            <TabsContent value="single">
              <RunConfigForm onSubmit={handleStart} isLoading={isLoading} sessionId={sessionId} onSessionIdChange={setSessionId} initialDomain={initialTopic} />
            </TabsContent>
            <TabsContent value="autonomous">
              <AutonomousForm onCycleStarted={setRunId} />
            </TabsContent>
          </Tabs>
        </>
      )}

      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {runId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Pipeline Progress</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline">Run #{runId}</Badge>
                {isCancelled ? (
                  <Badge className="bg-red-100 text-red-800" data-testid="cancelled-badge">
                    Cancelled
                  </Badge>
                ) : isComplete ? (
                  <Badge className="bg-success/10 text-success">Complete</Badge>
                ) : isConnected ? (
                  <Badge className="bg-info/10 text-info">Live</Badge>
                ) : (
                  <Badge variant="secondary">Connecting...</Badge>
                )}
                {isRunning && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleCancelClick}
                    disabled={isCancelling}
                    data-testid="cancel-run-btn"
                  >
                    {isCancelling ? "Cancelling…" : "Cancel Run"}
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <StageProgress stages={stages} currentStage={null} />
          </CardContent>

          {/* Cancel confirmation dialog (AR-01) */}
          {showCancelConfirm && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
              data-testid="cancel-confirm-dialog"
            >
              <Card className="w-full max-w-md mx-4">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-5 w-5 text-destructive" />
                    <CardTitle>Cancel Pipeline Run?</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    This will abort the running pipeline. Any stages that have already
                    completed will be preserved, but no further stages will execute.
                  </p>
                  {cancelError && (
                    <p className="text-sm text-destructive" data-testid="cancel-error">
                      {cancelError}
                    </p>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      onClick={handleCancelDismiss}
                      data-testid="cancel-dismiss-btn"
                    >
                      No, Continue
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={handleCancelConfirm}
                      disabled={isCancelling}
                      data-testid="cancel-confirm-btn"
                    >
                      {isCancelling ? "Cancelling…" : "Yes, Cancel Run"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {isComplete && (
            <CardContent className="border-t pt-4">
              <div className="flex items-center gap-2 text-success">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-medium">Pipeline completed successfully</span>
              </div>
            </CardContent>
          )}

          {isCancelled && (
            <CardContent className="border-t pt-4" data-testid="cancelled-partial-results">
              <div className="flex items-center gap-2 text-destructive">
                <XCircle className="h-5 w-5" />
                <span className="font-medium">Pipeline run was cancelled</span>
              </div>
              {hasPartialResults && (
                <p className="text-sm text-muted-foreground mt-1">
                  {completedStages.length} of {stages.length} stage{completedStages.length !== 1 ? "s" : ""} completed before cancellation.
                </p>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {(isComplete || isCancelled) && (
        <div className="space-y-4" data-testid="pipeline-results">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {isComplete ? (
                    <>
                      <CheckCircle2 className="h-5 w-5 text-success" />
                      <CardTitle>Pipeline Complete</CardTitle>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-5 w-5 text-destructive" />
                      <CardTitle>Pipeline Cancelled</CardTitle>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  {ideas.length > 0 && (
                    <span className="flex items-center gap-1">
                      <Lightbulb className="h-4 w-4" />
                      {ideas.length} idea{ideas.length !== 1 ? "s" : ""} generated
                    </span>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {ideasError && (
                <div className="flex items-center gap-2 text-destructive" data-testid="ideas-error">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">{ideasError}</span>
                </div>
              )}

              {ideasLoading && (
                <p className="text-sm text-muted-foreground">Loading results…</p>
              )}

              {!ideasLoading && !ideasError && ideas.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  {isCancelled
                    ? "No ideas were generated before cancellation."
                    : "No ideas generated in this run."}
                </p>
              )}

              {!ideasLoading && ideas.length > 0 && (
                <div className="space-y-3">
                  {ideas.map((idea) => (
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

              <div className="flex items-center gap-3 mt-4 pt-4 border-t">
                <Button variant="outline" onClick={() => navigate("/ideas")} data-testid="view-all-ideas">
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
