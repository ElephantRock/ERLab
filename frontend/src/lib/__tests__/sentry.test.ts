/**
 * Tests for BATCH-52 TASK-02: Sentry React SDK initialization.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock @sentry/react so no real Sentry calls are made
vi.mock("@sentry/react", () => ({
  init: vi.fn(),
  captureException: vi.fn(),
}));

// Ensure VITE_SENTRY_DSN is not set
const originalEnv = import.meta.env.VITE_SENTRY_DSN;

describe("initSentry", () => {
  beforeEach(() => {
    vi.resetModules();
    // Clear the env var
    delete import.meta.env.VITE_SENTRY_DSN;
  });

  it("TEST-52-07: initSentry returns false when VITE_SENTRY_DSN is not set", async () => {
    const { initSentry } = await import("@/lib/sentry");
    const result = initSentry();
    expect(result).toBe(false);
  });

  it("TEST-52-08: initSentry returns true and calls Sentry.init when DSN is set", async () => {
    import.meta.env.VITE_SENTRY_DSN = "https://example@sentry.io/123";
    const { initSentry } = await import("@/lib/sentry");
    const Sentry = await import("@sentry/react");

    const result = initSentry();
    expect(result).toBe(true);
    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: "https://example@sentry.io/123",
        tracesSampleRate: 0.1,
      }),
    );

    // Clean up
    delete import.meta.env.VITE_SENTRY_DSN;
  });

  // F1.6.3 [V3-5]: Sentry browser automatic capture is DISABLED so the
  // governed diagnostics endpoint remains the single transport.
  it("F1.6.3: init passes defaultIntegrations:false", async () => {
    import.meta.env.VITE_SENTRY_DSN = "https://example@sentry.io/123";
    const { initSentry } = await import("@/lib/sentry");
    const Sentry = await import("@sentry/react");
    initSentry();
    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({ defaultIntegrations: false }),
    );
    delete import.meta.env.VITE_SENTRY_DSN;
  });

  it("F1.6.3: init passes integrations:[] (no automatic integrations)", async () => {
    import.meta.env.VITE_SENTRY_DSN = "https://example@sentry.io/123";
    const { initSentry } = await import("@/lib/sentry");
    const Sentry = await import("@sentry/react");
    initSentry();
    const call = vi.mocked(Sentry.init).mock.calls.at(-1)?.[0] as Record<string, unknown>;
    expect(Array.isArray(call.integrations)).toBe(true);
    expect((call.integrations as unknown[]).length).toBe(0);
    delete import.meta.env.VITE_SENTRY_DSN;
  });
});
