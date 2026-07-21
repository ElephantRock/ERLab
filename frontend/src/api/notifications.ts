import { apiFetchUnchecked } from "./client";
import type { NotificationListResponse } from "./types";

export function getNotifications(params?: {
  limit?: number;
  offset?: number;
  read?: boolean;
}): Promise<NotificationListResponse> {
  const search = new URLSearchParams();
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  if (params?.read !== undefined) search.set("read", String(params.read));
  const qs = search.toString();
  return apiFetchUnchecked(`/notifications/${qs ? `?${qs}` : ""}`);
}

export function markRead(id: number): Promise<Record<string, unknown>> {
  return apiFetchUnchecked(`/notifications/${id}/read`, { method: "PATCH" });
}

export function markAllRead(): Promise<{ updated: number }> {
  return apiFetchUnchecked("/notifications/read-all", { method: "POST" });
}
