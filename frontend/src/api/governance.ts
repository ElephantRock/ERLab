/**
 * Governance API Client — BATCH-20/TASK-01
 *
 * Typed functions for governance approval endpoints.
 * Endpoint shapes from backend/api/routes/governance.py:
 *   GET  /governance/pending          → {pending: [{id, type, summary}]}
 *   POST /governance/{id}/approve     → {status, decision_id}
 *   POST /governance/{id}/deny        → {status, decision_id, amendment}
 */

import { apiFetchUnchecked } from "./client";
import { callContract } from "./contracts/common";
import { getPendingContract } from "./contracts/dashboard";

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
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(getPendingContract) as Promise<PendingResponse>;
}

/** Approve a pending governance decision by its ID. */
export function approveDecision(id: string): Promise<ApproveResponse> {
  return apiFetchUnchecked<ApproveResponse>(`/governance/${id}/approve`, {
    method: "POST",
  });
}

/** Deny a pending governance decision with an optional amendment. */
export function denyDecision(id: string, amendment?: string): Promise<DenyResponse> {
  return apiFetchUnchecked<DenyResponse>(`/governance/${id}/deny`, {
    method: "POST",
    body: JSON.stringify({ amendment: amendment ?? null }),
  });
}

// ── Idea-scoped governance decisions ────────────────────────────

export type GovernanceDecisionType = "approved" | "denied" | "needs_changes";

export interface GovernanceDecisionEntry {
  id: number;
  idea_id: number;
  decision: GovernanceDecisionType;
  reviewer: string;
  note: string | null;
  created_at: string;
}

export interface GovernanceDecisionListResponse {
  decisions: GovernanceDecisionEntry[];
  total: number;
}

export interface TimelineEvent {
  type: "decision" | "section_revision" | "comment";
  timestamp: string;
  actor: string;
  summary: string;
  detail: Record<string, unknown>;
}

export interface TimelineResponse {
  events: TimelineEvent[];
  total: number;
}

export function createGovernanceDecision(
  ideaId: number,
  decision: GovernanceDecisionType,
  note?: string,
): Promise<GovernanceDecisionEntry> {
  return apiFetchUnchecked(`/ideas/${ideaId}/governance/decision`, {
    method: "POST",
    body: JSON.stringify({ decision, note: note ?? null }),
  });
}

export function listGovernanceDecisions(
  ideaId: number,
): Promise<GovernanceDecisionListResponse> {
  return apiFetchUnchecked(`/ideas/${ideaId}/governance/decisions`);
}

export function getGovernanceTimeline(
  ideaId: number,
): Promise<TimelineResponse> {
  return apiFetchUnchecked(`/ideas/${ideaId}/governance/timeline`);
}
