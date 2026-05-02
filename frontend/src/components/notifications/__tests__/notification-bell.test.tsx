import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NotificationBell } from "@/components/notifications/notification-bell";

// Mock the API module
vi.mock("@/api/notifications", () => ({
  getNotifications: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}));

import { getNotifications, markRead, markAllRead } from "@/api/notifications";

const mockGetNotifications = vi.mocked(getNotifications);
const mockMarkRead = vi.mocked(markRead);
const mockMarkAllRead = vi.mocked(markAllRead);

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders bell with unread badge", async () => {
    mockGetNotifications.mockResolvedValue({
      notifications: [
        { id: 1, user_id: null, type: "pipeline.completed", title: "Pipeline completed", message: "Run done", read: false, created_at: "2026-05-02T12:00:00Z" },
      ],
      total: 1,
    });
    render(<NotificationBell />);
    const bell = screen.getByTestId("notification-bell");
    expect(bell).toBeDefined();
    await waitFor(() => {
      expect(screen.getByTestId("unread-badge")).toBeDefined();
    });
  });

  it("badge count shows correct number", async () => {
    mockGetNotifications.mockResolvedValue({
      notifications: [
        { id: 1, user_id: null, type: "info", title: "A", message: "a", read: false, created_at: "2026-05-02T12:00:00Z" },
        { id: 2, user_id: null, type: "info", title: "B", message: "b", read: false, created_at: "2026-05-02T12:00:00Z" },
        { id: 3, user_id: null, type: "info", title: "C", message: "c", read: true, created_at: "2026-05-02T12:00:00Z" },
      ],
      total: 3,
    });
    render(<NotificationBell />);
    await waitFor(() => {
      const badge = screen.getByTestId("unread-badge");
      expect(badge.textContent).toBe("3");
    });
  });

  it("click marks notification as read", async () => {
    mockGetNotifications.mockResolvedValue({
      notifications: [
        { id: 1, user_id: null, type: "pipeline.completed", title: "Completed", message: "Run done", read: false, created_at: "2026-05-02T12:00:00Z" },
      ],
      total: 1,
    });
    mockMarkRead.mockResolvedValue({ id: 1, read: true });
    render(<NotificationBell />);

    // Open dropdown
    await waitFor(() => {
      expect(screen.getByTestId("unread-badge")).toBeDefined();
    });
    fireEvent.click(screen.getByTestId("notification-bell"));

    // Click on notification item
    await waitFor(() => {
      expect(screen.getByTestId("notification-item-1")).toBeDefined();
    });
    fireEvent.click(screen.getByTestId("notification-item-1"));
    expect(mockMarkRead).toHaveBeenCalledWith(1);
  });

  it("mark all as read button works", async () => {
    mockGetNotifications.mockResolvedValue({
      notifications: [
        { id: 1, user_id: null, type: "info", title: "A", message: "a", read: false, created_at: "2026-05-02T12:00:00Z" },
      ],
      total: 1,
    });
    mockMarkAllRead.mockResolvedValue({ updated: 1 });
    render(<NotificationBell />);

    await waitFor(() => {
      expect(screen.getByTestId("unread-badge")).toBeDefined();
    });
    fireEvent.click(screen.getByTestId("notification-bell"));

    await waitFor(() => {
      expect(screen.getByTestId("mark-all-read")).toBeDefined();
    });
    fireEvent.click(screen.getByTestId("mark-all-read"));
    expect(mockMarkAllRead).toHaveBeenCalled();
  });
});
