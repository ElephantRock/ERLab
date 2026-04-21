import { useState } from "react";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import { AutonomousForm } from "@/components/pipeline/autonomous-form";
import { StageProgress } from "@/components/pipeline/stage-progress";
import { usePipelineProgress } from "@/hooks/usePipelineProgress";
import { triggerRun } from "@/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { PipelineRunRequest } from "@/api/types";
import { CheckCircle2 } from "lucide-react";

export default function PipelineNew() {
  const [runId, setRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { stages, isComplete, isConnected } = usePipelineProgress(runId);

  async function handleStart(config: PipelineRunRequest) {
    setIsLoading(true);
    setError(null);
    try {
      const res = await triggerRun(config);
      setRunId(res.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start pipeline");
    } finally {
      setIsLoading(false);
    }
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
    </div>
  );
}
