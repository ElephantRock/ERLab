import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  ApiError,
  apiFetchUnchecked,
  apiFetchBlob,
  apiFetchFormData,
  sseFetch,
  getApiUrl,
  getApiKey,
  buildUrl,
  buildAuthHeaders,
} from "@/api/client";

describe("getApiUrl / getApiKey — single source of truth", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("getApiUrl returns localStorage value or empty string", () => {
    expect(getApiUrl()).toBe("");
    localStorage.setItem("erock_api_url", "http://localhost:8000");
    expect(getApiUrl()).toBe("http://localhost:8000");
  });

  it("getApiKey returns localStorage value or empty string", () => {
    expect(getApiKey()).toBe("");
    localStorage.setItem("erock_api_key", "secret123");
    expect(getApiKey()).toBe("secret123");
  });
});

describe("buildUrl", () => {
  it("constructs URL from base + prefix + path", () => {
    localStorage.setItem("erock_api_url", "http://localhost:8000");
    expect(buildUrl("/test")).toBe("http://localhost:8000/api/v1/test");
  });

  it("uses empty base when not configured", () => {
    localStorage.clear();
    expect(buildUrl("/test")).toBe("/api/v1/test");
  });
});

describe("buildAuthHeaders", () => {
  beforeEach(() => localStorage.clear());

  it("includes X-API-Key when key is set", () => {
    localStorage.setItem("erock_api_key", "my-key");
    const headers = buildAuthHeaders();
    expect(headers["X-API-Key"]).toBe("my-key");
  });

  it("omits X-API-Key when not set", () => {
    const headers = buildAuthHeaders();
    expect(headers["X-API-Key"]).toBeUndefined();
  });

  it("merges extra headers", () => {
    localStorage.setItem("erock_api_key", "my-key");
    const headers = buildAuthHeaders({ Accept: "application/pdf" });
    expect(headers["X-API-Key"]).toBe("my-key");
    expect(headers["Accept"]).toBe("application/pdf");
  });
});

describe("apiFetchUnchecked", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("returns typed JSON on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: 1, name: "test" }), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const data = await apiFetchUnchecked<{ id: number; name: string }>("/test");
    expect(data).toEqual({ id: 1, name: "test" });
  });

  it("throws ApiError on non-OK response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Bad request" }), { status: 400 }),
    );
    try {
      await apiFetchUnchecked("/test");
      expect.unreachable("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(400);
      expect((err as ApiError).detail).toBe("Bad request");
    }
  });

  it("throws on 204 response (F1.1a seal: apiFetchUnchecked delegates to apiFetchJson which rejects 204)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiFetchUnchecked("/test")).rejects.toThrow(/204/);
  });

  it("injects X-API-Key header when key is in localStorage", async () => {
    localStorage.setItem("erock_api_key", "my-secret-key");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    await apiFetchUnchecked("/test");
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBe("my-secret-key");
  });

  it("omits X-API-Key when no key in localStorage", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    await apiFetchUnchecked("/test");
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBeUndefined();
  });
});

describe("apiFetchBlob", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("returns Blob for binary response", async () => {
    const blobData = new Blob(["fake-pdf-content"], { type: "application/pdf" });
    const mockResponse = {
      ok: true,
      status: 200,
      blob: vi.fn().mockResolvedValue(blobData),
      json: vi.fn(),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as any);
    const result = await apiFetchBlob("/export/pdf", {
      method: "POST",
      body: JSON.stringify({ idea_id: 1 }),
    });
    expect(result).toBe(blobData);
  });

  it("throws ApiError on non-OK response", async () => {
    const mockResponse = {
      ok: false,
      status: 404,
      json: vi.fn().mockResolvedValue({ detail: "Not found" }),
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as any);
    try {
      await apiFetchBlob("/export/pdf", { method: "POST", body: "{}" });
      expect.unreachable("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(404);
    }
  });

  it("injects X-API-Key for blob fetch", async () => {
    localStorage.setItem("erock_api_key", "blob-key");
    const blobData = new Blob(["x"], { type: "application/pdf" });
    const mockResponse = {
      ok: true,
      status: 200,
      blob: vi.fn().mockResolvedValue(blobData),
      json: vi.fn(),
    };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(mockResponse as any);
    await apiFetchBlob("/export/pdf", { method: "POST", body: "{}" });
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBe("blob-key");
  });
});

describe("apiFetchFormData", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("sends FormData with auth header, no explicit Content-Type", async () => {
    localStorage.setItem("erock_api_key", "form-key");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    const formData = new FormData();
    formData.append("file", new File(["test"], "test.pdf"));

    await apiFetchFormData("/knowledge/ingest", formData);

    const call = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const opts = call[1] as RequestInit;
    expect(opts.body).toBe(formData);
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBe("form-key");
    // Content-Type should NOT be set — browser sets multipart boundary
    expect((opts.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });
});

describe("sseFetch with Last-Event-ID", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("sends X-API-Key header when key is in localStorage", async () => {
    localStorage.setItem("erock_api_key", "key123");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );
    const controller = sseFetch("/test", { onEvent: vi.fn() });
    controller.abort();
    await new Promise((r) => setTimeout(r, 10));
    expect(fetchSpy).toHaveBeenCalled();
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBe("key123");
  });

  it("omits X-API-Key when no key in localStorage", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );
    const controller = sseFetch("/test", { onEvent: vi.fn() });
    controller.abort();
    await new Promise((r) => setTimeout(r, 10));
    expect(fetchSpy).toHaveBeenCalled();
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["X-API-Key"]).toBeUndefined();
  });

  it("does not include api_key in URL query params (HB-01)", async () => {
    localStorage.setItem("erock_api_key", "secret-key");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );
    const controller = sseFetch("/pipeline/runs/test/progress", { onEvent: vi.fn() });
    controller.abort();
    await new Promise((r) => setTimeout(r, 10));
    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).not.toContain("api_key");
    expect(url).not.toContain("secret-key");
  });

  it("sends Last-Event-ID header when provided", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );
    const controller = sseFetch(
      "/pipeline/runs/test/progress",
      { onEvent: vi.fn() },
      { lastEventId: "42" },
    );
    controller.abort();
    await new Promise((r) => setTimeout(r, 10));
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["Last-Event-ID"]).toBe("42");
  });

  it("omits Last-Event-ID when not provided", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 200 }),
    );
    const controller = sseFetch("/test", { onEvent: vi.fn() });
    controller.abort();
    await new Promise((r) => setTimeout(r, 10));
    const opts = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((opts.headers as Record<string, string>)["Last-Event-ID"]).toBeUndefined();
  });

  it("calls onEventId when SSE event has id: field", async () => {
    // Create a ReadableStream that emits one SSE event with an id
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode("id: 99\ndata: {\"type\":\"progress\"}\n\n"));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(stream, { status: 200 }),
    );
    const onEventId = vi.fn();
    const onEvent = vi.fn();
    sseFetch("/test", { onEvent, onEventId });
    await new Promise((r) => setTimeout(r, 50));
    expect(onEvent).toHaveBeenCalledWith('{"type":"progress"}');
    expect(onEventId).toHaveBeenCalledWith("99");
  });
});

describe("no duplicated localStorage reads outside client.ts", () => {
  it("knowledge.ts does not read localStorage directly", () => {
    // Read the source file via Node fs, not fetch (which is mocked)
    const fs = require("fs");
    const path = require("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../knowledge.ts"),
      "utf-8",
    );
    expect(source).not.toContain("localStorage");
  });

  it("exports.ts does not read localStorage directly", () => {
    const fs = require("fs");
    const path = require("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../exports.ts"),
      "utf-8",
    );
    expect(source).not.toContain("localStorage");
  });
});
