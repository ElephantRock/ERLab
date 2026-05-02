import { useState, useEffect } from "react";
import {
  triggerAutonomous,
  getAutonomousHistory,
  stopAutonomousCycle,
  getEvolutionStatus,
  startScheduler,
  stopScheduler,
  getSchedulerStatus,
  type EvolutionStatus,
  type SchedulerStatus,
} from "@/api/autonomous";
import { ConsciousnessStateBadge } from "@/components/autonomous/consciousness-state";
import { CycleProgress } from "@/components/autonomous/cycle-progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Cpu, Loader2, AlertCircle, Play, StopCircle, Clock, Activity } from "lucide-react";
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

  // Scheduler + evolution state
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [evolutionStatus, setEvolutionStatus] = useState<EvolutionStatus | null>(null);
  const [schedulerLoading, setSchedulerLoading] = useState(false);

  useEffect(() => {
    loadHistory();
    loadSchedulerAndEvolution();
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

  async function loadSchedulerAndEvolution() {
    try {
      const [sched, evo] = await Promise.all([
        getSchedulerStatus(),
        getEvolutionStatus(),
      ]);
      setSchedulerStatus(sched);
      setEvolutionStatus(evo);
    } catch {
      // Non-fatal
    }
  }

  async function handleSchedulerStart() {
    setSchedulerLoading(true);
    setError(null);
    try {
      await startScheduler();
      await loadSchedulerAndEvolution();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start scheduler");
    } finally {
      setSchedulerLoading(false);
    }
  }

  async function handleSchedulerStop() {
    setSchedulerLoading(true);
    setError(null);
    try {
      await stopScheduler();
      await loadSchedulerAndEvolution();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop scheduler");
    } finally {
      setSchedulerLoading(false);
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

      {/* Scheduler Controls */}
      <Card data-testid="scheduler-controls">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Scheduler
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">Status:</span>
            <span data-testid="scheduler-status-text">
              {schedulerStatus?.status ?? "unknown"}
            </span>
          </div>
          {schedulerStatus?.status === "running" && schedulerStatus.next_run && (
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">Next Run:</span>
              <span>{new Date(schedulerStatus.next_run).toLocaleString()}</span>
            </div>
          )}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleSchedulerStart}
              disabled={schedulerLoading || schedulerStatus?.status === "running"}
              variant="outline"
              data-testid="scheduler-start-btn"
            >
              {schedulerLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Play className="h-4 w-4 mr-2" />}
              Start Scheduler
            </Button>
            <Button
              onClick={handleSchedulerStop}
              disabled={schedulerLoading || schedulerStatus?.status !== "running"}
              variant="destructive"
              data-testid="scheduler-stop-btn"
            >
              <StopCircle className="h-4 w-4 mr-2" />
              Stop Scheduler
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Evolution Status */}
      <Card data-testid="evolution-status-card">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Evolution Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium">Enabled:</span>
              <span data-testid="evolution-enabled">
                {evolutionStatus?.enabled ? "Yes" : "No"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium">Overlays:</span>
              <span data-testid="evolution-overlays">
                {evolutionStatus?.overlays_generated ?? 0}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium">Recent Outcomes:</span>
              <span data-testid="evolution-outcomes">
                {evolutionStatus?.recent_outcomes?.length ?? 0}
              </span>
            </div>
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
