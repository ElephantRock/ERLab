import { useState, useEffect } from "react";
import { triggerAutonomous, getAutonomousHistory, stopAutonomousCycle } from "@/api/autonomous";
import { ConsciousnessStateBadge } from "@/components/autonomous/consciousness-state";
import { CycleProgress } from "@/components/autonomous/cycle-progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Cpu, Loader2, AlertCircle, Play, StopCircle } from "lucide-react";
import type { AutonomousCycleHistoryEntry, ConsciousnessState } from "@/api/autonomous";

export default function AutonomousPage() {
  const [cycles, setCycles] = useState<AutonomousCycleHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState("AI/NLP");
  const [maxRuns, setMaxRuns] = useState(3);
  const [consciousnessState, setConsciousnessState] = useState<ConsciousnessState>("idle");
  const [stopConfirmId, setStopConfirmId] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const data = await getAutonomousHistory();
      setCycles(data.cycles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleStart() {
    setIsStarting(true);
    setError(null);
    try {
      await triggerAutonomous({ domain, max_runs: maxRuns });
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start cycle");
    } finally {
      setIsStarting(false);
    }
  }

  function handleStopRequest(cycleId: string) {
    // HB-01: Require confirmation before stopping
    setStopConfirmId(cycleId);
  }

  async function handleStopConfirm(cycleId: string) {
    setStopConfirmId(null);
    try {
      await stopAutonomousCycle(cycleId);
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop cycle");
    }
  }

  function handleStopCancel() {
    setStopConfirmId(null);
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="autonomous-loading">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">Loading autonomous cycles...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="autonomous-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Autonomous Cycles</h1>
          <p className="text-muted-foreground">Monitor and control autonomous research cycles.</p>
        </div>
        <div data-testid="consciousness-display">
          <ConsciousnessStateBadge state={consciousnessState} />
        </div>
      </div>

      {error && (
        <Card className="border-destructive" data-testid="autonomous-error">
          <CardContent className="p-4 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
          </CardContent>
        </Card>
      )}

      {/* Start Cycle Form */}
      <Card data-testid="autonomous-start-form">
        <CardHeader>
          <CardTitle className="text-lg">Start New Cycle</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium" data-testid="domain-label">Domain</label>
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                data-testid="domain-input"
              />
            </div>
            <div className="w-32">
              <label className="text-sm font-medium">Max Runs</label>
              <input
                type="number"
                value={maxRuns}
                onChange={(e) => setMaxRuns(Number(e.target.value))}
                min={1}
                max={20}
                className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                data-testid="max-runs-input"
              />
            </div>
            <Button
              onClick={handleStart}
              disabled={isStarting}
              data-testid="start-cycle-btn"
            >
              {isStarting ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              {isStarting ? "Starting..." : "Start Cycle"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Stop Confirmation (HB-01) */}
      {stopConfirmId && (
        <Card className="border-yellow-500" data-testid="stop-confirm-dialog">
          <CardContent className="p-4">
            <p className="text-sm font-medium mb-3">
              Are you sure you want to stop cycle <code className="text-xs">{stopConfirmId}</code>?
            </p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleStopConfirm(stopConfirmId)}
                data-testid="stop-confirm-btn"
              >
                <StopCircle className="h-4 w-4 mr-1" />
                Confirm Stop
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleStopCancel}
                data-testid="stop-cancel-btn"
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* History List */}
      <div>
        <h2 className="text-lg font-semibold mb-3" data-testid="history-heading">Cycle History</h2>
        {cycles.length === 0 ? (
          <Card data-testid="autonomous-empty">
            <CardContent className="p-8 flex flex-col items-center gap-4">
              <Cpu className="h-12 w-12 text-muted-foreground" />
              <p className="text-muted-foreground">No autonomous cycles yet. Start one above.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3" data-testid="autonomous-history-list">
            {cycles.map((cycle) => (
              <CycleProgress
                key={cycle.cycle_id}
                cycle={cycle}
                onStop={handleStopRequest}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
