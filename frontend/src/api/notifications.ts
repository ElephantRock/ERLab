import { apiFetch } from "./client";
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
  return apiFetch(`/notifications/${qs ? `?${qs}` : ""}`);
}

export function markRead(id: number): Promise<Record<string, unknown>> {
  return apiFetch(`/notifications/${id}/read`, { method: "PATCH" });
}

export function markAllRead(): Promise<{ updated: number }> {
  return apiFetch("/notifications/read-all", { method: "POST" });
}
