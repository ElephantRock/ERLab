/**
 * F1.3a — Read endpoint contracts (settings, plugins, knowledge graph,
 * autonomous, notifications, comments, revisions, certification, overrides,
 * gap clusters).
 *
 * Migrates 15 read endpoints from apiFetchUnchecked to JsonContract with
 * runtime decoders. Each decoder validates material fields (IDs, counts,
 * statuses, array structure). For complex nested types, the decoder is
 * declared against the full domain type via the decodeObject<T> type
 * parameter and only the material fields are listed in `required` —
 * decodeObject preserves unknown fields via its forward-compat spread and
 * casts the output to T.
 *
 * Backend sources:
 *   GET /status/detailed                          → DetailedStatus
 *   GET /status/evolution                         → EvolutionStatus
 *   GET /auth/users                               → AuthUser[]
 *   GET /plugins/                                 → { plugins: Plugin[], total }
 *   GET /gaps/clusters                            → { clusters: [...], total_papers }
 *   GET /knowledge-graph/stats                    → GraphStats
 *   GET /knowledge-graph/entities                 → GraphEntity[]
 *   GET /knowledge-graph/world-model              → WorldModel
 *   GET /pipeline/autonomous/history              → { cycles: [...] }
 *   GET /pipeline/scheduler/status                → SchedulerStatus
 *   GET /notifications/                           → NotificationListResponse
 *   GET /ideas/{ideaId}/comments                  → CommentListResponse
 *   GET /ideas/{ideaId}/sections/{key}/revisions  → RevisionHistoryResponse
 *   GET /settings/certification                   → CertificationResponse
 *   GET /settings/overrides                       → OverridesResponse
 */

import {
  ApiContractError,
  decodeArray,
  decodeBoolean,
  decodeEnum,
  decodeNumber,
  decodeObject,
  decodeString,
  decodeStringRecord,
  type JsonContract,
  type ResponseDecoder,
} from "./common";
import type { DetailedStatus } from "@/api/client";
import type {
  EvolutionStatus,
  AutonomousCycleHistoryEntry,
  AutonomousHistoryResponse,
  SchedulerStatus,
} from "@/api/autonomous";
import type { AuthUser } from "@/api/auth";
import type { Plugin, PluginListResponse } from "@/api/exports";
import type {
  GraphStats,
  GraphEntity,
  GraphRelationship,
  WorldModel,
} from "@/api/knowledge-graph";
import type { Notification, NotificationListResponse, RevisionEntry, RevisionHistoryResponse } from "@/api/types";
import type { CommentItem, CommentListResponse } from "@/api/collaboration";
import type {
  CertificationEntry,
  CertificationResponse,
  OverridesResponse,
} from "@/api/settings";
import type { SystemStatus } from "@/api/types";

// ── Settings: DetailedStatus ─────────────────────────────────────────
// All three fields are material (drive Settings UI) — strict required.

export const getDetailedStatusContract: JsonContract<DetailedStatus> = {
  id: "status.getDetailedStatus",
  method: "GET",
  pathPattern: "/status/detailed",
  responseKind: "json",
  decoder: decodeObject<DetailedStatus>({
    required: {
      version: decodeString,
      provider: decodeString,
      db_status: decodeString,
    },
  }),
};

// ── Settings: EvolutionStatus ────────────────────────────────────────
// Material fields: enabled (UI toggle), overlays_generated (count),
// recent_outcomes (array structure with stage_name + score).

const evolutionOutcomeDecoder = decodeObject<{
  stage_name: string;
  score: number;
  run_id: string;
}>({
  required: {
    stage_name: decodeString,
    score: decodeNumber,
    run_id: decodeString,
  },
});

export const getEvolutionStatusContract: JsonContract<EvolutionStatus> = {
  id: "status.getEvolutionStatus",
  method: "GET",
  pathPattern: "/status/evolution",
  responseKind: "json",
  decoder: decodeObject<EvolutionStatus>({
    required: {
      enabled: decodeBoolean,
      overlays_generated: decodeNumber,
      recent_outcomes: decodeArray(evolutionOutcomeDecoder),
    },
  }),
};

// ── Settings: AuthUser list ──────────────────────────────────────────
// Material fields: id (key), username (display), role (perm decisions).
// role is a closed enum ("admin" | "user") validated via decodeEnum.

const authUserDecoder = decodeObject<AuthUser>({
  required: {
    id: decodeNumber,
    username: decodeString,
    email: decodeString,
    role: decodeEnum<AuthUser["role"]>(["admin", "user"]),
  },
});

export const listUsersContract: JsonContract<AuthUser[]> = {
  id: "auth.listUsers",
  method: "GET",
  pathPattern: "/auth/users",
  responseKind: "json",
  decoder: decodeArray(authUserDecoder),
};

// ── Plugins: PluginListResponse ──────────────────────────────────────
// Material fields: plugins[].name + enabled, total count.

const pluginDecoder = decodeObject<Plugin>({
  required: {
    name: decodeString,
    version: decodeString,
    description: decodeString,
    enabled: decodeBoolean,
  },
});

export const listPluginsContract: JsonContract<PluginListResponse> = {
  id: "plugins.listPlugins",
  method: "GET",
  pathPattern: "/plugins/",
  responseKind: "json",
  decoder: decodeObject<PluginListResponse>({
    required: {
      plugins: decodeArray(pluginDecoder),
      total: decodeNumber,
    },
  }),
};

// ── Gaps: clusters ───────────────────────────────────────────────────
// The page (gaps-explorer.tsx) consumes clusterData.clusters as unknown[]
// (passed to ClusterScatterPlot via `as never[]`) and clusterData.total_papers
// as a number for display. Material fields: clusters (array of objects) and
// total_papers (count for display). Each cluster item is validated as a
// non-null object so downstream rendering sees structured values, not
// primitives. The per-cluster shape is opaque to the page; the decoder
// preserves all cluster fields via decodeObject's forward-compat spread.

export interface GapClustersResponse {
  clusters: Record<string, unknown>[];
  total_papers: number;
}

const gapClusterItemDecoder = decodeObject<Record<string, unknown>>({
  required: {},
});

export const getGapClustersContract: JsonContract<GapClustersResponse> = {
  id: "gaps.getGapClusters",
  method: "GET",
  pathPattern: "/gaps/clusters",
  responseKind: "json",
  decoder: decodeObject<GapClustersResponse>({
    required: {
      clusters: decodeArray(gapClusterItemDecoder),
      total_papers: decodeNumber,
    },
  }),
};

// ── Knowledge graph: GraphStats ──────────────────────────────────────
// Material fields: counts (entity_count, relationship_count). Type
// distribution records are nested and forward-compat — left as passthrough.

export const getGraphStatsContract: JsonContract<GraphStats> = {
  id: "knowledgeGraph.getGraphStats",
  method: "GET",
  pathPattern: "/knowledge-graph/stats",
  responseKind: "json",
  decoder: decodeObject<GraphStats>({
    required: {
      entity_count: decodeNumber,
      relationship_count: decodeNumber,
    },
  }),
};

// ── Knowledge graph: GraphEntity list ────────────────────────────────
// Material fields: id (key), entity_type, name (display). aliases is an
// array of strings. properties/truth are nested — preserved via the
// forward-compat spread.

const graphEntityDecoder = decodeObject<GraphEntity>({
  required: {
    id: decodeString,
    entity_type: decodeString,
    name: decodeString,
    aliases: decodeArray(decodeString),
  },
});

export const getEntitiesContract: JsonContract<GraphEntity[]> = {
  id: "knowledgeGraph.getEntities",
  method: "GET",
  pathPattern: "/knowledge-graph/entities",
  responseKind: "json",
  decoder: decodeArray(graphEntityDecoder),
};

// ── Knowledge graph: WorldModel ──────────────────────────────────────
// Material fields: top-level totals + array structure for top_entities and
// strongest_relationships. Distribution records are nested passthrough.

const graphRelationshipDecoder = decodeObject<GraphRelationship>({
  required: {
    source_id: decodeString,
    target_id: decodeString,
    relation_type: decodeString,
    weight: decodeNumber,
    evidence: decodeArray(decodeString),
  },
});

export const getWorldModelContract: JsonContract<WorldModel> = {
  id: "knowledgeGraph.getWorldModel",
  method: "GET",
  pathPattern: "/knowledge-graph/world-model",
  responseKind: "json",
  decoder: decodeObject<WorldModel>({
    required: {
      total_entities: decodeNumber,
      total_relationships: decodeNumber,
      top_entities: decodeArray(graphEntityDecoder),
      strongest_relationships: decodeArray(graphRelationshipDecoder),
    },
  }),
};

// ── Autonomous: history ──────────────────────────────────────────────
// Material fields: cycle_id (key), runs (count), status (drives display).
// status is a closed enum validated via decodeEnum.

const autonomousCycleDecoder = decodeObject<AutonomousCycleHistoryEntry>({
  required: {
    cycle_id: decodeString,
    domain: decodeString,
    runs: decodeNumber,
    status: decodeEnum<AutonomousCycleHistoryEntry["status"]>([
      "running",
      "completed",
      "stopped",
    ]),
  },
});

export const getAutonomousHistoryContract: JsonContract<AutonomousHistoryResponse> = {
  id: "autonomous.getAutonomousHistory",
  method: "GET",
  pathPattern: "/pipeline/autonomous/history",
  responseKind: "json",
  decoder: decodeObject<AutonomousHistoryResponse>({
    required: {
      cycles: decodeArray(autonomousCycleDecoder),
    },
  }),
};

// ── Autonomous: scheduler status ─────────────────────────────────────
// Material fields: status (drives UI state). next_run / interval_seconds
// are optional.

export const getSchedulerStatusContract: JsonContract<SchedulerStatus> = {
  id: "autonomous.getSchedulerStatus",
  method: "GET",
  pathPattern: "/pipeline/scheduler/status",
  responseKind: "json",
  decoder: decodeObject<SchedulerStatus>({
    required: {
      status: decodeString,
    },
    optional: {
      next_run: decodeString,
      interval_seconds: decodeNumber,
    },
  }),
};

// ── Notifications: list ──────────────────────────────────────────────
// Material fields: id, type, title, read. total drives pagination display.
// user_id is required by the type but nullable — preserved via spread.

const notificationDecoder = decodeObject<Notification>({
  required: {
    id: decodeNumber,
    type: decodeString,
    title: decodeString,
    message: decodeString,
    read: decodeBoolean,
    created_at: decodeString,
  },
});

export const getNotificationsContract: JsonContract<NotificationListResponse> = {
  id: "notifications.getNotifications",
  method: "GET",
  pathPattern: "/notifications/",
  responseKind: "json",
  decoder: decodeObject<NotificationListResponse>({
    required: {
      notifications: decodeArray(notificationDecoder),
      total: decodeNumber,
    },
  }),
};

// ── Comments: list ───────────────────────────────────────────────────
// Material fields: id (key), author (display), content (display).
// parent_id is required by CommentItem but nullable — preserved via spread.

const commentDecoder = decodeObject<CommentItem>({
  required: {
    id: decodeNumber,
    idea_id: decodeNumber,
    author: decodeString,
    content: decodeString,
    created_at: decodeString,
  },
});

export const listCommentsContract: JsonContract<CommentListResponse> = {
  id: "collaboration.listComments",
  method: "GET",
  pathPattern: "/ideas/{ideaId}/comments",
  responseKind: "json",
  decoder: decodeObject<CommentListResponse>({
    required: {
      comments: decodeArray(commentDecoder),
      total: decodeNumber,
    },
  }),
};

// ── Revisions: section history ───────────────────────────────────────
// Material fields: revisions[].id (key) + section_hash (content identity) +
// created_at + is_current. current_hash on the envelope. RevisionEntry has
// deeply nested optional quality_summary and model_receipt sub-objects —
// validated as passthrough via the forward-compat spread.

const revisionEntryDecoder = decodeObject<RevisionEntry>({
  required: {
    id: decodeNumber,
    source: decodeString,
    trigger: decodeString,
    section_hash: decodeString,
    created_at: decodeString,
    is_current: decodeBoolean,
  },
});

export const getSectionRevisionsContract: JsonContract<RevisionHistoryResponse> = {
  id: "ideas.getSectionRevisions",
  method: "GET",
  pathPattern: "/ideas/{ideaId}/sections/{sectionKey}/revisions",
  responseKind: "json",
  decoder: decodeObject<RevisionHistoryResponse>({
    required: {
      revisions: decodeArray(revisionEntryDecoder),
      current_hash: decodeString,
    },
  }),
};

// ── Certification: list ──────────────────────────────────────────────
// Material fields: certifications[].model_id (key) + provider + status,
// total count. allowed_stages is a required Record<string,string> on the
// type — preserved via spread.

const certificationEntryDecoder = decodeObject<CertificationEntry>({
  required: {
    model_id: decodeString,
    provider: decodeString,
    status: decodeString,
  },
});

export const getCertificationContract: JsonContract<CertificationResponse> = {
  id: "settings.getCertification",
  method: "GET",
  pathPattern: "/settings/certification",
  responseKind: "json",
  decoder: decodeObject<CertificationResponse>({
    required: {
      certifications: decodeArray(certificationEntryDecoder),
      total: decodeNumber,
    },
  }),
};

// ── Overrides: list ──────────────────────────────────────────────────
// Material fields: overrides is a Record<string,string> (stage → model_id),
// total count. decodeStringRecord validates every value is a string.

export const getOverridesContract: JsonContract<OverridesResponse> = {
  id: "settings.getOverrides",
  method: "GET",
  pathPattern: "/settings/overrides",
  responseKind: "json",
  decoder: decodeObject<OverridesResponse>({
    required: {
      overrides: decodeStringRecord,
      total: decodeNumber,
    },
  }),
};

// ── Status: platform status (GET /) ──────────────────────────────────
// SystemStatus identity fields: app_name, version. config is a record of
// mixed boolean/string values (per backend status.py: provider flags +
// default_provider string). defaults is a record of numbers. Both records
// are validated value-by-value so a malformed payload is rejected rather
// than silently cast.

const statusConfigDecoder: ResponseDecoder<Record<string, boolean | string>> = {
  decode(value, ctx) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `expected object (config record), got ${value === null ? "null" : Array.isArray(value) ? "array" : typeof value}`,
        200,
      );
    }
    const obj = value as Record<string, unknown>;
    const out: Record<string, boolean | string> = {};
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v === "boolean" || typeof v === "string") {
        out[k] = v;
      } else {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `config value for key ${JSON.stringify(k)} expected boolean|string, got ${typeof v}`,
          200,
        );
      }
    }
    return out;
  },
};

const statusDefaultsDecoder: ResponseDecoder<Record<string, number>> = {
  decode(value, ctx) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new ApiContractError(
        "api_response_contract_mismatch",
        ctx.endpointId,
        `expected object (defaults record), got ${value === null ? "null" : Array.isArray(value) ? "array" : typeof value}`,
        200,
      );
    }
    const obj = value as Record<string, unknown>;
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(obj)) {
      if (typeof v !== "number" || Number.isNaN(v)) {
        throw new ApiContractError(
          "api_response_contract_mismatch",
          ctx.endpointId,
          `defaults value for key ${JSON.stringify(k)} expected number, got ${typeof v}`,
          200,
        );
      }
      out[k] = v;
    }
    return out;
  },
};

export const getStatusContract: JsonContract<SystemStatus> = {
  id: "status.getStatus",
  method: "GET",
  pathPattern: "/status",
  responseKind: "json",
  decoder: decodeObject<SystemStatus>({
    required: {
      app_name: decodeString,
      version: decodeString,
      config: statusConfigDecoder,
      defaults: statusDefaultsDecoder,
    },
  }),
};
