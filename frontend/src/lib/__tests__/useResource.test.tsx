/**
 * Tests for useResource (INTERFACE_CONTRACT §1).
 *
 * Verifies the four-state discriminated union contract:
 * - loading: initial fetch in flight
 * - ready: success with non-empty data
 * - error: failure, with a reachable retry closure
 * - empty: success where isEmpty matched
 *
 * And the structural guarantees:
 * - errors never throw to the caller (they become state)
 * - retry re-invokes the fetcher
 * - empty is distinct from ready
 * - impossible states are unrepresentable (type-checked, but we verify
 *   the runtime behavior: no loading+error, no data-without-ready)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useResource } from "@/lib/useResource";

// ── Test harness ──────────────────────────────────────────────────────

/** Fresh QueryClient per test to avoid cross-test cache contamination. */
function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

// ── loading ───────────────────────────────────────────────────────────

describe("useResource — loading state", () => {
  it("returns loading while the fetch is in flight", async () => {
    let resolve: (v: string[]) => void = () => {};
    const fetcher = () =>
      new Promise<string[]>((r) => {
        resolve = r;
      });

    const { result } = renderHook(() => useResource(["k"], fetcher), {
      wrapper: createWrapper(),
    });

    expect(result.current.status).toBe("loading");
    resolve(["done"]);
    await waitFor(() => expect(result.current.status).toBe("ready"));
  });
});

// ── ready ─────────────────────────────────────────────────────────────

describe("useResource — ready state", () => {
  it("returns ready with data on a non-empty success", async () => {
    const fetcher = vi.fn().mockResolvedValue(["a", "b"]);
    const { result } = renderHook(() => useResource(["k1"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("ready"));
    if (result.current.status !== "ready") throw new Error("unreachable");
    expect(result.current.data).toEqual(["a", "b"]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("returns ready for object data that isn't empty-shaped", async () => {
    const fetcher = vi.fn().mockResolvedValue({ name: "thing", value: 42 });
    const { result } = renderHook(() => useResource(["k2"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("ready"));
    if (result.current.status !== "ready") throw new Error("unreachable");
    expect(result.current.data).toEqual({ name: "thing", value: 42 });
  });
});

// ── empty ─────────────────────────────────────────────────────────────

describe("useResource — empty state", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("treats [] as empty by default", async () => {
    const fetcher = vi.fn().mockResolvedValue([]);
    const { result } = renderHook(() => useResource(["e1"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("empty"));
    if (result.current.status !== "empty") throw new Error("unreachable");
    expect(result.current.data).toEqual([]);
  });

  it("treats { total: 0 } as empty by default", async () => {
    const fetcher = vi.fn().mockResolvedValue({ total: 0, ideas: [] });
    const { result } = renderHook(() => useResource(["e2"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("empty"));
  });

  it("respects a custom isEmpty predicate", async () => {
    // A non-empty list, but the predicate forces empty.
    const fetcher = vi.fn().mockResolvedValue([1, 2, 3]);
    const { result } = renderHook(
      () => useResource(["e3"], fetcher, { isEmpty: () => true }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.status).toBe("empty"));
  });

  it("does NOT treat a non-empty list as empty", async () => {
    const fetcher = vi.fn().mockResolvedValue([1, 2, 3]);
    const { result } = renderHook(() => useResource(["e4"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("ready"));
  });
});

// ── error ─────────────────────────────────────────────────────────────

describe("useResource — error state", () => {
  it("surfaces a thrown error as { status: error } — never throws to the caller", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useResource(["x1"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    if (result.current.status !== "error") throw new Error("unreachable");
    expect(result.current.error.message).toBe("boom");
    // The defining structural property: retry is reachable from render,
    // so the error cannot be silently swallowed.
    expect(typeof result.current.retry).toBe("function");
  });

  it("retry re-invokes the fetcher and can recover", async () => {
    let call = 0;
    const fetcher = vi.fn(() => {
      call += 1;
      return call === 1
        ? Promise.reject(new Error("first fails"))
        : Promise.resolve(["recovered"]);
    });

    const { result } = renderHook(() => useResource(["x2"], fetcher), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    if (result.current.status !== "error") throw new Error("unreachable");

    result.current.retry();
    await waitFor(() => expect(result.current.status).toBe("ready"));
    if (result.current.status !== "ready") throw new Error("unreachable");
    expect(result.current.data).toEqual(["recovered"]);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

// ── enabled ───────────────────────────────────────────────────────────

describe("useResource — enabled gate", () => {
  it("stays loading when enabled is false", async () => {
    const fetcher = vi.fn().mockResolvedValue(["x"]);
    const { result } = renderHook(
      () => useResource(["g1"], fetcher, { enabled: false }),
      { wrapper: createWrapper() },
    );

    // With enabled:false the query never fires; status stays loading.
    expect(result.current.status).toBe("loading");
    expect(fetcher).not.toHaveBeenCalled();
  });
});
