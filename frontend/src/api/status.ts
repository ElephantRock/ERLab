import { apiFetchUnchecked } from "./client";
import type { SystemStatus } from "./types";

export function getSystemStatus(): Promise<SystemStatus> {
  return apiFetchUnchecked("/status");
}
