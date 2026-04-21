import { apiFetch } from "./client";
import type { SystemStatus } from "./types";

export function getSystemStatus(): Promise<SystemStatus> {
  return apiFetch("/status");
}
