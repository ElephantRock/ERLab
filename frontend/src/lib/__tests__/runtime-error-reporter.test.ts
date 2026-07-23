/**
 * F1.6.1 reporter tests.
 *
 * F1.6.1 [V3-2] F1.6.1 [V3-impl-qualification-1] requirements under test:
 *   - reportRuntimeError returns event_id SYNCHRONOUSLY
 *   - reportRuntimeError never throws (TOTAL FUNCTION)
 *   - AbortError → no transport call, event_id still returned
 *   - first occurrence → transport call made (fire-and-forget)
 *   - duplicate (same Error identity) → no second transport call
 *   - transport failure swallowed (no rejection propagated)
 *   - internal collaborator failures handled (sanitizer/registry throw)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the transport so reporter tests don't hit the network.
vi.mock("@/api/clients/diagnostics-client", () => ({
  sendRuntimeErrorReport: vi.fn(),
}));

// Mock the registry to control dedup behavior.
vi.mock("@/lib/runtime-error-registry", () => ({
  registerIncident: vi.fn((_error, _ctx, eventId) => ({
    eventId,
    shouldSend: true,
  })),
  clearRouteScope: vi.fn(),
}));

import { reportRuntimeError, isFilteredError } from "@/lib/runtime-error-reporter";
import { sendRuntimeErrorReport } from "@/api/clients/diagnostics-client";
import { registerIncident } from "@/lib/runtime-error-registry";

const mockSend = vi.mocked(sendRuntimeErrorReport);
const mockRegister = vi.mocked(registerIncident);

describe("reportRuntimeError (F1.6.1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSend.mockResolvedValue({ status: "accepted", event_id: "evt-1" });
    mockRegister.mockImplementation((_e, _c, eventId) => ({
      eventId,
      shouldSend: true,
    }));
  });

  it("returns an event_id synchronously (no await needed)", () => {
    const result = reportRuntimeError(new Error("x"), {
      category: "render_error",
      route: "/",
    });
    // No await — result is a string.
    expect(typeof result).toBe("string");
    expect(result.startsWith("evt-")).toBe(true);
  });

  it("sends the report via transport on first occurrence", () => {
    reportRuntimeError(new Error("x"), {
      category: "render_error",
      route: "/dashboard",
    });
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it("does NOT send on duplicate (registry said shouldSend:false)", () => {
    mockRegister.mockImplementationOnce(() => ({
      eventId: "evt-canonical",
      shouldSend: false,
    }));
    reportRuntimeError(new Error("x"), {
      category: "render_error",
      route: "/",
    });
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("returns the canonical event_id from the registry (not the fallback)", () => {
    mockRegister.mockImplementationOnce(() => ({
      eventId: "evt-canonical-from-prior-channel",
      shouldSend: false,
    }));
    const id = reportRuntimeError(new Error("x"), {
      category: "render_error",
      route: "/",
    });
    expect(id).toBe("evt-canonical-from-prior-channel");
  });

  it("AbortError → no transport call, event_id still returned", () => {
    const abort = new DOMException("aborted", "AbortError");
    const id = reportRuntimeError(abort, {
      category: "unhandled_rejection",
      route: "/",
    });
    expect(typeof id).toBe("string");
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("AbortError via Error subclass name → filtered", () => {
    const err = new Error("x");
    err.name = "AbortError";
    reportRuntimeError(err, { category: "global_error", route: "/" });
    expect(mockSend).not.toHaveBeenCalled();
  });

  it("transport rejection swallowed (no throw, event_id still returned)", async () => {
    mockSend.mockRejectedValueOnce(new Error("network down"));
    const id = reportRuntimeError(new Error("x"), {
      category: "global_error",
      route: "/",
    });
    expect(typeof id).toBe("string");
    // Allow microtasks to flush — the swallowed rejection should not
    // surface as an unhandled rejection.
    await new Promise((r) => setTimeout(r, 0));
  });

  it("ApiError is NOT filtered — it gets reported if it reaches the reporter", () => {
    class ApiError extends Error {
      name = "ApiError";
      constructor(public status: number, public detail: string) {
        super(detail);
      }
    }
    reportRuntimeError(new ApiError(500, "boom"), {
      category: "unhandled_rejection",
      route: "/",
    });
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it("ApiContractError is NOT filtered — it gets reported", () => {
    class ApiContractError extends Error {
      name = "ApiContractError";
    }
    reportRuntimeError(new ApiContractError(), {
      category: "unhandled_rejection",
      route: "/",
    });
    expect(mockSend).toHaveBeenCalledTimes(1);
  });
});

describe("reportRuntimeError total-function safety (V3-impl-qualification-1)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("never throws when registerIncident throws", () => {
    mockRegister.mockImplementation(() => {
      throw new Error("registry explosion");
    });
    expect(() =>
      reportRuntimeError(new Error("x"), { category: "render_error", route: "/" }),
    ).not.toThrow();
  });

  it("never throws when sanitizer throws (sendRuntimeErrorReport is called with a sanitized report — if sanitizer throws internally the catch handles it)", () => {
    // Force the sanitizer to throw by passing malformed context.
    mockSend.mockResolvedValue({ status: "accepted", event_id: "evt-1" });
    expect(() =>
      reportRuntimeError(new Error("x"), {
        category: "render_error",
        // Pass undefined route — sanitizer should handle, but if it
        // throws the outer try/catch in the reporter catches it.
        route: null as unknown as string,
      }),
    ).not.toThrow();
  });

  it("never throws when transport invocation throws synchronously", () => {
    mockSend.mockImplementation(() => {
      throw new Error("sync transport explosion");
    });
    expect(() =>
      reportRuntimeError(new Error("x"), { category: "render_error", route: "/" }),
    ).not.toThrow();
  });

  it("always returns a string event_id (the fallback on internal failure)", () => {
    mockRegister.mockImplementation(() => {
      throw new Error("total registry failure");
    });
    const id = reportRuntimeError(new Error("x"), {
      category: "render_error",
      route: "/",
    });
    expect(typeof id).toBe("string");
    expect(id.startsWith("evt-")).toBe(true);
  });
});

describe("isFilteredError", () => {
  it("true for Error with name AbortError", () => {
    const e = new Error("x");
    e.name = "AbortError";
    expect(isFilteredError(e)).toBe(true);
  });

  it("true for DOMException AbortError", () => {
    const e = new DOMException("aborted", "AbortError");
    expect(isFilteredError(e)).toBe(true);
  });

  it("true for error with __handled marker", () => {
    const e = new Error("x") as Error & { __handled?: boolean };
    e.__handled = true;
    expect(isFilteredError(e)).toBe(true);
  });

  it("false for generic Error", () => {
    expect(isFilteredError(new Error("x"))).toBe(false);
  });

  it("false for ApiError-like errors (instanceof check not required)", () => {
    class ApiError extends Error {
      name = "ApiError";
    }
    expect(isFilteredError(new ApiError())).toBe(false);
  });

  it("false for non-Error values (string, object)", () => {
    expect(isFilteredError("string error")).toBe(false);
    expect(isFilteredError({ message: "obj" })).toBe(false);
  });
});
