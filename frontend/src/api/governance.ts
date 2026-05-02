/**
 * Governance API Client — BATCH-20/TASK-01
 *
 * Typed functions for governance approval endpoints.
 * Endpoint shapes from backend/api/routes/governance.py:
 *   GET  /governance/pending          → {pending: [{id, type, summary}]}
 *   POST /governance/{id}/approve     → {status, decision_id}
 *   POST /governance/{id}/deny        → {status, decision_id, amendment}
 */

import { apiFetch } from "./client";

// ── Types ────────────────────────────────────────────────────────

export interface PendingApproval {
  id: string;
  type: string;
  summary: string;
}

export interface PendingResponse {
  pending: PendingApproval[];
}

export interface ApproveResponse {
  status: "approved";
  decision_id: string;
}

export interface DenyResponse {
  status: "denied";
  decision_id: string;
  amendment: string | null;
}

// ── API Functions ────────────────────────────────────────────────

/** Fetch all pending governance approvals. */
export function getPending(): Promise<PendingResponse> {
  return apiFetch<PendingResponse>("/governance/pending");
}

/** Approve a pending governance decision by its ID. */
export function approveDecision(id: string): Promise<ApproveResponse> {
  return apiFetch<ApproveResponse>(`/governance/${id}/approve`, {
    method: "POST",
  });
}

/** Deny a pending governance decision with an optional amendment. */
export function denyDecision(id: string, amendment?: string): Promise<DenyResponse> {
  return apiFetch<DenyResponse>(`/governance/${id}/deny`, {
    method: "POST",
    body: JSON.stringify({ amendment: amendment ?? null }),
  });
}
