/**
 * Governance API Client — BATCH-20/TASK-01
 *
 * Typed functions for governance approval endpoints.
 * Endpoint shapes from backend/api/routes/governance.py:
 *   GET  /governance/pending          → {pending: [{id, type, summary}]}
 *   POST /governance/{id}/approve     → {status, decision_id}
 *   POST /governance/{id}/deny        → {status, decision_id, amendment}
 */

import { callContract } from "./contracts/common";
import { getPendingContract } from "./contracts/dashboard";
import {
  approveDecisionContract,
  createGovernanceDecisionContract,
  denyDecisionContract,
  getGovernanceTimelineContract,
  listGovernanceDecisionsContract,
} from "./contracts/governance";

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
  return callContract(approveDecisionContract, { params: { id } });
}

/** Deny a pending governance decision with an optional amendment. */
export function denyDecision(id: string, amendment?: string): Promise<DenyResponse> {
  return callContract(denyDecisionContract, {
    params: { id },
    body: { amendment: amendment ?? null },
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
  return callContract(createGovernanceDecisionContract, {
    params: { ideaId },
    body: { decision, note: note ?? null },
  });
}

export function listGovernanceDecisions(
  ideaId: number,
): Promise<GovernanceDecisionListResponse> {
  return callContract(listGovernanceDecisionsContract, {
    params: { ideaId },
  });
}

export function getGovernanceTimeline(
  ideaId: number,
): Promise<TimelineResponse> {
  return callContract(getGovernanceTimelineContract, {
    params: { ideaId },
  });
}
