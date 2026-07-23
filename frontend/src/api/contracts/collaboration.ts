/**
 * F1.7a — Collaboration endpoint contracts (addComment, createShareLink,
 * getSharedIdea).
 *
 * Migrates the three remaining apiFetchUnchecked callers in
 * src/api/collaboration.ts to JsonContract + runtime decoders. The list
 * endpoint (listComments) was already migrated in F1.3a; this completes the
 * domain. Material fields: comment id/author/content, share token + url,
 * shared idea title/domain. `parent_id` is required on CommentItem but
 * nullable, so it is preserved via the forward-compat spread rather than
 * validated (decodeObject skips null optionals).
 *
 * Backend sources (backend/api/routes/collaboration.py):
 *   POST /ideas/{idea_id}/comments → CommentItem
 *   POST /ideas/{idea_id}/share     → ShareLinkResponse
 *   GET  /shared/{token}            → { idea: {...} }
 */

import type {
  CommentItem,
  ShareLinkResponse,
  SharedIdeaResponse,
} from "@/api/collaboration";
import {
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";

// ── Decoders ─────────────────────────────────────────────────────────

// CommentItem — material fields validated; parent_id is required-by-type but
// nullable from the backend, so it is preserved via the spread.
const commentItemDecoder = decodeObject<CommentItem>({
  required: {
    id: decodeNumber,
    idea_id: decodeNumber,
    author: decodeString,
    content: decodeString,
    created_at: decodeString,
  },
});

// ShareLinkResponse — all fields are material (id, idea_id, token, share_url,
// created_at).
const shareLinkResponseDecoder = decodeObject<ShareLinkResponse>({
  required: {
    id: decodeNumber,
    idea_id: decodeNumber,
    token: decodeString,
    share_url: decodeString,
    created_at: decodeString,
  },
});

// SharedIdeaResponse — nested idea object. Material fields: id, title,
// problem_statement, proposed_method, expected_contributions, domain,
// created_at. The three score fields and source_gap_ids are nullable —
// preserved via the spread.
const sharedIdeaDetailDecoder = decodeObject<
  SharedIdeaResponse["idea"]
>({
  required: {
    id: decodeNumber,
    title: decodeString,
    problem_statement: decodeString,
    proposed_method: decodeString,
    expected_contributions: decodeString,
    domain: decodeString,
    created_at: decodeString,
  },
});

const sharedIdeaResponseDecoder = decodeObject<SharedIdeaResponse>({
  required: {
    idea: sharedIdeaDetailDecoder,
  },
});

// ── Contracts ────────────────────────────────────────────────────────

export const addCommentContract: JsonContract<CommentItem> = {
  id: "collaboration.addComment",
  method: "POST",
  pathPattern: "/ideas/{ideaId}/comments",
  responseKind: "json",
  decoder: commentItemDecoder,
};

export const createShareLinkContract: JsonContract<ShareLinkResponse> = {
  id: "collaboration.createShareLink",
  method: "POST",
  pathPattern: "/ideas/{ideaId}/share",
  responseKind: "json",
  decoder: shareLinkResponseDecoder,
};

export const getSharedIdeaContract: JsonContract<SharedIdeaResponse> = {
  id: "collaboration.getSharedIdea",
  method: "GET",
  pathPattern: "/shared/{token}",
  responseKind: "json",
  decoder: sharedIdeaResponseDecoder,
};
