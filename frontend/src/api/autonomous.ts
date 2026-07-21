import { apiFetch } from "./client";
import type { AutonomousCycleResponse } from "./types";

/** Autonomous cycle history entry. */
export interface AutonomousCycleHistoryEntry {
  cycle_id: string;
  domain: string;
  runs: number;
  status: "running" | "completed" | "stopped";
}

/** Autonomous cycle history response. */
export interface AutonomousHistoryResponse {
  cycles: AutonomousCycleHistoryEntry[];
}

/** Stop a running autonomous cycle. HB-01: Requires explicit cycle_id. */
export function stopAutonomousCycle(cycleId: string): Promise<{ status: string; cycle_id: string }> {
  return apiFetch(`/pipeline/autonomous/stop?cycle_id=${encodeURIComponent(cycleId)}`, {
    method: "POST",
  });
}

/** Get autonomous cycle history. */
export function getAutonomousHistory(): Promise<AutonomousHistoryResponse> {
  return apiFetch("/pipeline/autonomous/history");
}

// F1.1 H2: getConsciousnessState() and the ConsciousnessState /
// ConsciousnessStateInfo types were removed. The function called
// /pipeline/autonomous/consciousness, which does not exist in the backend
// (no such route in backend/api/routes/pipeline.py). The orchestrator has
// an internal consciousness state machine but it is not exposed via API.
// The page (autonomous.tsx) imported the type but hardcoded "idle" and
// never called the function; the ConsciousnessStateBadge component
// rendered a badge for a state that was always "idle". All dead — removed.

/** Evolution status response from GET /status/evolution. */
export interface EvolutionStatus {
  enabled: boolean;
  overlays_generated: number;
  recent_outcomes: Array<{
    stage_name: string;
    score: number;
    run_id: string;
  }>;
}

/** Get evolution status from the backend. */
export function getEvolutionStatus(): Promise<EvolutionStatus> {
  return apiFetch("/status/evolution");
}

/** Scheduler status response. */
export interface SchedulerStatus {
  status: string;
  next_run?: string;
  interval_seconds?: number;
}

/** Start the autonomous pipeline scheduler. */
export function startScheduler(): Promise<{ status: string; interval_seconds?: number }> {
  return apiFetch("/pipeline/scheduler/start", { method: "POST" });
}

/** Stop the autonomous pipeline scheduler. */
export function stopScheduler(): Promise<{ status: string }> {
  return apiFetch("/pipeline/scheduler/stop", { method: "POST" });
}

/** Get scheduler status. */
export function getSchedulerStatus(): Promise<SchedulerStatus> {
  return apiFetch("/pipeline/scheduler/status");
}

/** Re-export triggerAutonomous from pipeline.ts for convenience. */
export { triggerAutonomous } from "./pipeline";
export type { AutonomousCycleResponse };
