import { useState, useEffect, useRef, useCallback } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getNotifications, markRead, markAllRead } from "@/api/notifications";
import type { Notification } from "@/api/types";
import { toast } from "sonner";

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, now - then);
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function typeIcon(type: string): string {
  if (type.includes("completed")) return "✅";
  if (type.includes("failed")) return "❌";
  return "🔔";
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [, setTotal] = useState(0);
  const [fetchError, setFetchError] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchUnread = useCallback(async () => {
    try {
      const res = await getNotifications({ limit: 50, read: false });
      setUnreadCount(res.total);
      setFetchError(false);
    } catch {
      setFetchError(true);
    }
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const res = await getNotifications({ limit: 50 });
      setItems(res.notifications);
      setTotal(res.total);
      setUnreadCount(res.notifications.filter((n) => !n.read).length);
      setFetchError(false);
    } catch {
      setFetchError(true);
    }
  }, []);

  useEffect(() => {
    fetchUnread();
    const interval = setInterval(fetchUnread, 30_000);
    return () => clearInterval(interval);
  }, [fetchUnread]);

  useEffect(() => {
    if (open) fetchAll();
  }, [open, fetchAll]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleMarkAllRead = async () => {
    try {
      await markAllRead();
      setUnreadCount(0);
      setItems((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch {
      toast.error("Failed to mark notifications as read");
    }
  };

  const handleMarkRead = async (id: number) => {
    try {
      await markRead(id);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      toast.error("Failed to mark notification as read");
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 relative"
        onClick={() => setOpen((prev) => !prev)}
        data-testid="notification-bell"
      >
        <Bell className="h-4 w-4" />
        {fetchError ? (
          <span
            className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white"
            data-testid="unread-badge"
            title="Failed to load notifications"
          >
            !
          </span>
        ) : unreadCount > 0 ? (
          <span
            className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white"
            data-testid="unread-badge"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </Button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 max-h-96 overflow-y-auto rounded-md border bg-popover shadow-lg z-50">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-sm font-medium">Notifications</span>
            {unreadCount > 0 && (
              <button
                className="text-xs text-info hover:underline"
                onClick={handleMarkAllRead}
                data-testid="mark-all-read"
              >
                Mark all as read
              </button>
            )}
          </div>
          <div className="divide-y">
            {fetchError ? (
              <div
                className="px-3 py-4 text-center text-sm text-destructive"
                data-testid="notifications-error"
              >
                Failed to load notifications
              </div>
            ) : items.length === 0 && (
              <div className="px-3 py-4 text-center text-sm text-muted-foreground">
                No notifications
              </div>
            )}
            {items.map((n) => (
              <button
                key={n.id}
                className={`w-full text-left px-3 py-2 hover:bg-accent/50 transition-colors ${
                  !n.read ? "bg-accent/20" : ""
                }`}
                onClick={() => {
                  if (!n.read) handleMarkRead(n.id);
                }}
                data-testid={`notification-item-${n.id}`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-sm mt-0.5">{typeIcon(n.type)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium truncate">{n.title}</span>
                      {!n.read && (
                        <span className="h-2 w-2 rounded-full bg-info flex-shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">{n.message}</p>
                    <span className="text-[10px] text-muted-foreground">{timeAgo(n.created_at)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
