import {
  callContract,
  decodeBoolean,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./contracts/common";
import { getNotificationsContract } from "./contracts/f1-3a-reads";
import type { Notification, NotificationListResponse } from "./types";

export function getNotifications(params?: {
  limit?: number;
  offset?: number;
  read?: boolean;
}): Promise<NotificationListResponse> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(getNotificationsContract, { query: params });
}

// ── Mark-read mutations (F1.7a) ───────────────────────────────────────
//
// Backend (backend/api/routes/notifications.py):
//   PATCH /notifications/{id}/read → the updated notification object
//        (id, user_id, type, title, message, read, created_at)
//   POST  /notifications/read-all   → { updated: N } (count updated)
//
// The bell component awaits these for success/error but does not read the
// response body — it invalidates the getNotifications query on success.
// The contracts still validate the material fields so a malformed response
// surfaces as ApiContractError rather than a silent cast.

const markReadResultDecoder = decodeObject<Notification>({
  required: {
    id: decodeNumber,
    type: decodeString,
    title: decodeString,
    message: decodeString,
    read: decodeBoolean,
    created_at: decodeString,
  },
});

const markReadContract: JsonContract<Notification> = {
  id: "notifications.markRead",
  method: "PATCH",
  pathPattern: "/notifications/{id}/read",
  responseKind: "json",
  decoder: markReadResultDecoder,
};

const markAllReadContract: JsonContract<{ updated: number }> = {
  id: "notifications.markAllRead",
  method: "POST",
  pathPattern: "/notifications/read-all",
  responseKind: "json",
  decoder: decodeObject<{ updated: number }>({
    required: { updated: decodeNumber },
  }),
};

/**
 * Mark a single notification as read. Returns the updated notification.
 * F1.7a: migrated from apiFetchUnchecked to callContract with a runtime
 * decoder (was previously an unvalidated `Record<string, unknown>` cast).
 */
export function markRead(id: number): Promise<Notification> {
  return callContract(markReadContract, { params: { id } });
}

/**
 * Mark all notifications as read for the current user. Returns the count
 * updated. F1.7a: migrated from apiFetchUnchecked to callContract.
 */
export function markAllRead(): Promise<{ updated: number }> {
  return callContract(markAllReadContract);
}
