import { apiFetchUnchecked } from "./client";
import { callContract } from "./contracts/common";
import { getNotificationsContract } from "./contracts/f1-3a-reads";
import type { NotificationListResponse } from "./types";

export function getNotifications(params?: {
  limit?: number;
  offset?: number;
  read?: boolean;
}): Promise<NotificationListResponse> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(getNotificationsContract, { query: params });
}

export function markRead(id: number): Promise<Record<string, unknown>> {
  return apiFetchUnchecked(`/notifications/${id}/read`, { method: "PATCH" });
}

export function markAllRead(): Promise<{ updated: number }> {
  return apiFetchUnchecked("/notifications/read-all", { method: "POST" });
}
