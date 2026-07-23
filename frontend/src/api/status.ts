import { callContract } from "./contracts/common";
import { getStatusContract } from "./contracts/f1-3a-reads";
import type { SystemStatus } from "./types";

export function getSystemStatus(): Promise<SystemStatus> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(getStatusContract);
}
