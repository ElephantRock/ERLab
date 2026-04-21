import { describe, it, expect, beforeEach, vi } from "vitest";
import { ApiError, apiFetch, sseUrl } from "@/api/client";

describe("ApiError", () => {
  it("has correct properties", () => {
    const err = new ApiError(404, "Not found");
    expect(err.name).toBe("ApiError");
    expect(err.status).toBe(404);
    expect(err.detail).toBe("Not found");
    expect(err.message).toBe("Not found");
  });
});

describe("apiFetch", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("returns typed JSON on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 1, name: "test" }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const data = await apiFetch<{ id: number; name: string }>("/test");
    expect(data).toEqual({ id: 1, name: "test" });
  });

  it("throws ApiError on non-OK response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Bad request" }), { status: 400 }),
    );
    try {
      await apiFetch("/test");
      expect.unreachable("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(400);
      expect((err as ApiError).detail).toBe("Bad request");
    }
  });

  it("returns undefined for 204 response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    const data = await apiFetch("/test");
    expect(data).toBeUndefined();
  });

  it("injects X-API-Key header when key is in localStorage", async () => {
    localStorage.setItem("erock_api_key", "my-secret-key");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    await apiFetch("/test");
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBe("my-secret-key");
  });

  it("omits X-API-Key when no key in localStorage", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    await apiFetch("/test");
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBeUndefined();
  });
});

describe("sseUrl", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("constructs URL with api_key param", () => {
    localStorage.setItem("erock_api_key", "key123");
    const url = sseUrl("/pipeline/runs/1/progress");
    expect(url).toContain("/api/v1/pipeline/runs/1/progress");
    expect(url).toContain("api_key=key123");
  });

  it("constructs URL without api_key when no key set", () => {
    const url = sseUrl("/pipeline/runs/1/progress");
    expect(url).toContain("/api/v1/pipeline/runs/1/progress");
    expect(url).not.toContain("api_key");
  });

  it("uses window.location.origin as base when no custom URL", () => {
    const url = sseUrl("/test");
    expect(url).toContain("http");
  });
});
