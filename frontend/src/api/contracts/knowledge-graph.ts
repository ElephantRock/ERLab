/**
 * F1.7a — Knowledge-graph entity / subgraph endpoint contracts.
 *
 * Migrates the two remaining knowledge-graph reads from apiFetchUnchecked to
 * JsonContract with runtime decoders. The other KG reads (stats, entities,
 * world-model) already live in contracts/f1-3a-reads.ts and are the canonical
 * contracts for those endpoints.
 *
 * Backend sources (backend/api/routes/knowledge_graph.py):
 *   GET /knowledge-graph/entity/{id}    → { entity, relationships }
 *   GET /knowledge-graph/subgraph/{id}  → { entities, relationships }
 *
 * The GraphEntity / GraphRelationship shapes are serialized by
 * `_serialize_entity` / `_serialize_relationship`. Material identity fields
 * (entity id/entity_type/name/aliases; relationship source_id/target_id/
 * relation_type/weight/evidence) are validated strictly. The nested `truth`
 * sub-object and `properties` map are preserved via decodeObject's
 * forward-compat spread — they are consumed opaquely by the graph views.
 */

import {
  decodeArray,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";
import type {
  EntityDetail,
  GraphEntity,
  GraphRelationship,
  Subgraph,
} from "@/api/knowledge-graph";

// GraphEntity: material fields are id (key), entity_type, name (display),
// aliases (array of strings). properties and truth are nested — preserved
// via the forward-compat spread.
const graphEntityDecoder = decodeObject<GraphEntity>({
  required: {
    id: decodeString,
    entity_type: decodeString,
    name: decodeString,
    aliases: decodeArray(decodeString),
  },
});

// GraphRelationship: material fields are the endpoint IDs, relation_type,
// weight, and evidence array. truth is nested — preserved via spread.
const graphRelationshipDecoder = decodeObject<GraphRelationship>({
  required: {
    source_id: decodeString,
    target_id: decodeString,
    relation_type: decodeString,
    weight: decodeNumber,
    evidence: decodeArray(decodeString),
  },
});

export const getEntityContract: JsonContract<EntityDetail> = {
  id: "knowledgeGraph.getEntity",
  method: "GET",
  pathPattern: "/knowledge-graph/entity/{id}",
  responseKind: "json",
  decoder: decodeObject<EntityDetail>({
    required: {
      entity: graphEntityDecoder,
      relationships: decodeArray(graphRelationshipDecoder),
    },
  }),
};

export const getSubgraphContract: JsonContract<Subgraph> = {
  id: "knowledgeGraph.getSubgraph",
  method: "GET",
  pathPattern: "/knowledge-graph/subgraph/{id}",
  responseKind: "json",
  decoder: decodeObject<Subgraph>({
    required: {
      entities: decodeArray(graphEntityDecoder),
      relationships: decodeArray(graphRelationshipDecoder),
    },
  }),
};
