/**
 * F1.7a — Governance endpoint contracts.
 *
 * Migrates the governance mutation/read endpoints from apiFetchUnchecked to
 * JsonContract with runtime decoders. getPending already lives in
 * contracts/dashboard.ts (it was migrated in F1.3a) and remains the canonical
 * pending-list contract — it is not re-declared here.
 *
 * Backend sources (backend/api/routes/governance.py):
 *   POST /governance/{id}/approve                  → { status, decision_id }
 *   POST /governance/{id}/deny                     → { status, decision_id, amendment }
 *   POST /ideas/{idea_id}/governance/decision      → GovernanceDecisionEntry
 *   GET  /ideas/{idea_id}/governance/decisions     → { decisions: [...], total }
 *   GET  /ideas/{idea_id}/governance/timeline      → { events: [...], total }
 *
 * Material fields are validated strictly. The closed status enums
 * (approve/deny result, GovernanceDecisionType) are enforced via decodeEnum
 * so an unexpected backend value surfaces as a contract failure rather than
 * a silently-coerced status. TimelineEvent.detail is a free-form per-event
 * object — preserved via the forward-compat spread, not field-validated.
 */

import {
  decodeArray,
  decodeEnum,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";
import type {
  ApproveResponse,
  DenyResponse,
  GovernanceDecisionEntry,
  GovernanceDecisionListResponse,
  GovernanceDecisionType,
  TimelineEvent,
  TimelineResponse,
} from "@/api/governance";

// ── Status enums (closed vocabularies that drive UI state) ───────────

const approveStatusDecoder = decodeEnum<ApproveResponse["status"]>(["approved"]);
const denyStatusDecoder = decodeEnum<DenyResponse["status"]>(["denied"]);
const decisionTypeDecoder = decodeEnum<GovernanceDecisionType>([
  "approved",
  "denied",
  "needs_changes",
]);

// TimelineEvent.type is a closed vocabulary emitted by the backend
// (decision | section_revision | comment).
const timelineTypeDecoder = decodeEnum<TimelineEvent["type"]>([
  "decision",
  "section_revision",
  "comment",
]);

// ── Contracts ────────────────────────────────────────────────────────

export const approveDecisionContract: JsonContract<ApproveResponse> = {
  id: "governance.approveDecision",
  method: "POST",
  pathPattern: "/governance/{id}/approve",
  responseKind: "json",
  decoder: decodeObject<ApproveResponse>({
    required: {
      status: approveStatusDecoder,
      decision_id: decodeString,
    },
  }),
};

export const denyDecisionContract: JsonContract<DenyResponse> = {
  id: "governance.denyDecision",
  method: "POST",
  pathPattern: "/governance/{id}/deny",
  responseKind: "json",
  decoder: decodeObject<DenyResponse>({
    required: {
      status: denyStatusDecoder,
      decision_id: decodeString,
    },
    // amendment is `string | null`: the backend always includes it (it
    // returns the explicit amendment value, which may be null). Declaring it
    // optional means decodeObject validates it as a string when non-null and
    // preserves a null value via the forward-compat spread — matching the
    // declared type without rejecting the legitimate null case.
    optional: {
      amendment: decodeString,
    },
  }),
};

const governanceDecisionEntryDecoder = decodeObject<GovernanceDecisionEntry>({
  required: {
    id: decodeNumber,
    idea_id: decodeNumber,
    decision: decisionTypeDecoder,
    reviewer: decodeString,
    created_at: decodeString,
  },
  optional: {
    // note is nullable on the backend (str | None) — validated as a string
    // when present-and-non-null, preserved as null otherwise.
    note: decodeString,
  },
});

export const createGovernanceDecisionContract: JsonContract<GovernanceDecisionEntry> = {
  id: "governance.createGovernanceDecision",
  method: "POST",
  pathPattern: "/ideas/{ideaId}/governance/decision",
  responseKind: "json",
  decoder: governanceDecisionEntryDecoder,
};

export const listGovernanceDecisionsContract: JsonContract<GovernanceDecisionListResponse> = {
  id: "governance.listGovernanceDecisions",
  method: "GET",
  pathPattern: "/ideas/{ideaId}/governance/decisions",
  responseKind: "json",
  decoder: decodeObject<GovernanceDecisionListResponse>({
    required: {
      decisions: decodeArray(governanceDecisionEntryDecoder),
      total: decodeNumber,
    },
  }),
};

const timelineEventDecoder = decodeObject<TimelineEvent>({
  required: {
    type: timelineTypeDecoder,
    timestamp: decodeString,
    actor: decodeString,
    summary: decodeString,
  },
  // detail is a free-form per-event object (decision note, section hash,
  // comment preview, ...). It is always present from the backend but its
  // shape varies by event type — preserve via the forward-compat spread
  // rather than validating inner fields.
});

export const getGovernanceTimelineContract: JsonContract<TimelineResponse> = {
  id: "governance.getGovernanceTimeline",
  method: "GET",
  pathPattern: "/ideas/{ideaId}/governance/timeline",
  responseKind: "json",
  decoder: decodeObject<TimelineResponse>({
    required: {
      events: decodeArray(timelineEventDecoder),
      total: decodeNumber,
    },
  }),
};
