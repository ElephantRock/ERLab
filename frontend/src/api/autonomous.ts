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

/** Re-export triggerAutonomous from pipeline.ts for convenience. */
export { triggerAutonomous } from "./pipeline";
export type { AutonomousCycleResponse };
