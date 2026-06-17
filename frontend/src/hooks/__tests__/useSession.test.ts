/**
 * Tests for useSession hook
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSession } from "@/hooks/useSession";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("useSession", () => {
  it("returns empty string when no session stored", () => {
    const { result } = renderHook(() => useSession());
    expect(result.current.sessionId).toBe("");
  });

  it("loads session from localStorage on init", () => {
    localStorage.setItem("erock_session_id", "my-session");
    const { result } = renderHook(() => useSession());
    expect(result.current.sessionId).toBe("my-session");
  });

  it("setSessionId persists to localStorage", () => {
    const { result } = renderHook(() => useSession());
    act(() => result.current.setSessionId("new-session"));
    expect(result.current.sessionId).toBe("new-session");
    expect(localStorage.getItem("erock_session_id")).toBe("new-session");
  });

  it("setSessionId with empty string removes from localStorage", () => {
    localStorage.setItem("erock_session_id", "old");
    const { result } = renderHook(() => useSession());
    act(() => result.current.setSessionId(""));
    expect(result.current.sessionId).toBe("");
    expect(localStorage.getItem("erock_session_id")).toBeNull();
  });

  it("clearSession removes from localStorage", () => {
    localStorage.setItem("erock_session_id", "temp");
    const { result } = renderHook(() => useSession());
    act(() => result.current.clearSession());
    expect(result.current.sessionId).toBe("");
    expect(localStorage.getItem("erock_session_id")).toBeNull();
  });
});
