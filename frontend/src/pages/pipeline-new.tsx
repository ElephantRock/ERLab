import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import { AutonomousForm } from "@/components/pipeline/autonomous-form";
import { StageProgress } from "@/components/pipeline/stage-progress";
import { usePipelineProgress } from "@/hooks/usePipelineProgress";
import { triggerRun, getRunIdeas } from "@/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { PipelineRunRequest, IdeaSummary } from "@/api/types";
import { CheckCircle2, Lightbulb, AlertCircle } from "lucide-react";

export default function PipelineNew() {
  const navigate = useNavigate();
  const [runId, setRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<IdeaSummary[]>([]);
  const [ideasError, setIdeasError] = useState<string | null>(null);
  const [ideasLoading, setIdeasLoading] = useState(false);
  const { stages, isComplete, isConnected } = usePipelineProgress(runId);

  async function handleStart(config: PipelineRunRequest) {
    setIsLoading(true);
    setError(null);
    setIdeas([]);
    setIdeasError(null);
    try {
      const res = await triggerRun(config);
      setRunId(res.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start pipeline");
    } finally {
      setIsLoading(false);
    }
  }

  // Fetch ideas when pipeline completes
  useEffect(() => {
    if (!isComplete) return;

    // runId is the string run identifier (e.g. run_20260502_143000).
    // We need the numeric DB id to fetch ideas. Parse it from the SSE stream
    // or fall back to listing runs and finding the latest.
    async function fetchIdeas() {
      setIdeasLoading(true);
      setIdeasError(null);
      try {
        // The run_id string from triggerRun is not the DB id.
        // We fetch ideas by listing recent runs and finding our match.
        const { listRuns } = await import("@/api/pipeline");
        const runsData = await listRuns({ limit: 1 });
        if (runsData.runs.length > 0) {
          const latestRun = runsData.runs[0];
          const ideasData = await getRunIdeas(latestRun.id);
          setIdeas(ideasData.ideas);
        }
      } catch (err) {
        setIdeasError(err instanceof Error ? err.message : "Failed to load results");
      } finally {
        setIdeasLoading(false);
      }
    }

    fetchIdeas();
  }, [isComplete]);

  function handleReset() {
    setRunId(null);
    setIdeas([]);
    setIdeasError(null);
    setError(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pipeline</h1>
        <p className="text-muted-foreground">Configure and launch a research pipeline.</p>
      </div>

      {!runId && (
        <Tabs defaultValue="single">
          <TabsList>
            <TabsTrigger value="single">Single Run</TabsTrigger>
            <TabsTrigger value="autonomous">Autonomous Cycle</TabsTrigger>
          </TabsList>
          <TabsContent value="single">
            <RunConfigForm onSubmit={handleStart} isLoading={isLoading} />
          </TabsContent>
          <TabsContent value="autonomous">
            <AutonomousForm onCycleStarted={setRunId} />
          </TabsContent>
        </Tabs>
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
              <CardTitle className="text-lg">Pipeline Progress</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline">Run #{runId}</Badge>
                {isComplete ? (
                  <Badge className="bg-green-100 text-green-800">Complete</Badge>
                ) : isConnected ? (
                  <Badge className="bg-blue-100 text-blue-800">Live</Badge>
                ) : (
                  <Badge variant="secondary">Connecting...</Badge>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <StageProgress stages={stages} currentStage={null} />
          </CardContent>

          {isComplete && (
            <CardContent className="border-t pt-4">
              <div className="flex items-center gap-2 text-green-700">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-medium">Pipeline completed successfully</span>
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {isComplete && (
        <div className="space-y-4" data-testid="pipeline-results">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <CardTitle className="text-lg">Pipeline Complete</CardTitle>
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
                <p className="text-sm text-muted-foreground">No ideas generated in this run.</p>
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
