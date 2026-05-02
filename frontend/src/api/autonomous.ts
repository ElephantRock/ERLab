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

/** Consciousness state enum matching backend ConsciousnessState. */
export type ConsciousnessState =
  | "idle"
  | "exploring"
  | "generating"
  | "evaluating"
  | "synthesizing"
  | "resting";

/** Consciousness state info from the backend. */
export interface ConsciousnessStateInfo {
  state: ConsciousnessState;
  seconds_in_state: number;
  next_action: string;
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

/** Get the current consciousness state. */
export function getConsciousnessState(): Promise<ConsciousnessStateInfo> {
  return apiFetch("/pipeline/autonomous/consciousness");
}

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
