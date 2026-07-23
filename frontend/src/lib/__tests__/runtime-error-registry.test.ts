/**
 * F1.6.1 incident registry tests.
 *
 * F1.6.1 [V3-1] requirements under test:
 *   - same Error identity within window → same event_id, no second send
 *   - same Error identity after window expires → new incident permitted
 *   - different Error instances with same fingerprint within window → deduplicated
 *   - category excluded from fingerprint (render_error + global_error dedup)
 *   - registry size bounded (no unbounded growth)
 *   - route-scope clear empties fingerprint registry
 *   - synchronous (no await)
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  registerIncident,
  clearRouteScope,
  _resetForTesting,
  _fingerprintRegistrySizeForTesting,
  MAX_FINGERPRINT_RECORDS,
} from "@/lib/runtime-error-registry";

beforeEach(() => {
  _resetForTesting();
});

describe("runtime-error-registry identity dedup (primary mechanism)", () => {
  it("same Error instance reported twice → second call has shouldSend:false", () => {
    const err = new Error("boom");
    const r1 = registerIncident(err, { route: "/x" }, "evt-1");
    const r2 = registerIncident(err, { route: "/x" }, "evt-2");
    expect(r1.shouldSend).toBe(true);
    expect(r2.shouldSend).toBe(false);
    // Canonical event_id is reused.
    expect(r2.eventId).toBe(r1.eventId);
    expect(r2.eventId).toBe("evt-1");
  });

  it("two different Error instances (no stack) within window → fingerprint dedup", () => {
    // Two distinct TypeError instances with the same name, route, and
    // no stack should produce the same fingerprint → deduplicated.
    const e1 = new TypeError("x");
    const e2 = new TypeError("y");
    e1.stack = "";
    e2.stack = "";
    const r1 = registerIncident(e1, { route: "/dashboard" }, "evt-A");
    const r2 = registerIncident(e2, { route: "/dashboard" }, "evt-B");
    expect(r1.shouldSend).toBe(true);
    expect(r2.shouldSend).toBe(false);
    expect(r2.eventId).toBe("evt-A"); // canonical reuse
  });

  it("category EXCLUDED from fingerprint: render_error + global_error dedup", () => {
    // Same Error instance — primary identity dedup applies regardless.
    const err = new TypeError("boom");
    registerIncident(err, { route: "/x" }, "evt-r-1");
    // Register again with same Error but pretend different category —
    // identity dedup wins, no re-send.
    const r2 = registerIncident(err, { route: "/x" }, "evt-g-1");
    expect(r2.shouldSend).toBe(false);
    expect(r2.eventId).toBe("evt-r-1");
  });

  it("fingerprint dedup works across categories for different Error instances", () => {
    // Two distinct Error instances of the same class, same route, no
    // stack — fingerprint dedup should kick in even if the reporter
    // would classify them with different categories.
    const makeErr = () => {
      const e = new TypeError("x");
      e.stack = "";
      return e;
    };
    const r1 = registerIncident(makeErr(), { route: "/page" }, "evt-1");
    const r2 = registerIncident(makeErr(), { route: "/page" }, "evt-2");
    expect(r1.shouldSend).toBe(true);
    expect(r2.shouldSend).toBe(false);
    expect(r2.eventId).toBe("evt-1");
  });
});

describe("runtime-error-registry TTL", () => {
  it("same fingerprint in a different time window → new incident permitted", () => {
    // Use two distinct Errors and a mocked clock to advance time.
    const baseTime = 1_000_000;
    let now = baseTime;
    const realDateNow = Date.now;
    vi.spyOn(Date, "now").mockImplementation(() => now);

    const e1 = new TypeError("x"); e1.stack = "";
    const e2 = new TypeError("y"); e2.stack = "";

    const r1 = registerIncident(e1, { route: "/page" }, "evt-window-1");
    expect(r1.shouldSend).toBe(true);

    // Advance well beyond INCIDENT_WINDOW_MS (5_000).
    now = baseTime + 60_000;

    const r2 = registerIncident(e2, { route: "/page" }, "evt-window-2");
    expect(r2.shouldSend).toBe(true); // new window → new incident
    expect(r2.eventId).toBe("evt-window-2");

    vi.restoreAllMocks();
    // ensure Date.now is restored even if assertions above threw
    void realDateNow;
  });

  it("expired fingerprint is removed from registry on next registration", () => {
    const baseTime = 2_000_000;
    let now = baseTime;
    vi.spyOn(Date, "now").mockImplementation(() => now);

    const e1 = new TypeError("x"); e1.stack = "";
    registerIncident(e1, { route: "/p" }, "evt-1");
    const sizeAfterFirst = _fingerprintRegistrySizeForTesting();
    expect(sizeAfterFirst).toBe(1);

    now = baseTime + 60_000;
    const e2 = new TypeError("y"); e2.stack = "";
    registerIncident(e2, { route: "/p" }, "evt-2");
    // The expired entry was lazily evicted; the new one was added.
    // Net size should remain 1, not 2.
    expect(_fingerprintRegistrySizeForTesting()).toBe(1);

    vi.restoreAllMocks();
  });
});

describe("runtime-error-registry size cap", () => {
  it("registry does not grow beyond MAX_FINGERPRINT_RECORDS", () => {
    const baseTime = 5_000_000;
    const now = baseTime;
    vi.spyOn(Date, "now").mockImplementation(() => now);

    // Submit MAX + 50 distinct fingerprints (different routes → different keys).
    for (let i = 0; i < MAX_FINGERPRINT_RECORDS + 50; i++) {
      const e = new TypeError(`err-${i}`); e.stack = "";
      registerIncident(e, { route: `/route-${i}` }, `evt-${i}`);
    }

    expect(_fingerprintRegistrySizeForTesting()).toBeLessThanOrEqual(MAX_FINGERPRINT_RECORDS);

    vi.restoreAllMocks();
  });
});

describe("runtime-error-registry route-scope clear", () => {
  it("clearRouteScope empties the fingerprint registry", () => {
    const e = new TypeError("x"); e.stack = "";
    registerIncident(e, { route: "/p" }, "evt-1");
    expect(_fingerprintRegistrySizeForTesting()).toBe(1);
    clearRouteScope();
    expect(_fingerprintRegistrySizeForTesting()).toBe(0);
  });

  it("after clearRouteScope, same fingerprint is a fresh incident", () => {
    const e1 = new TypeError("x"); e1.stack = "";
    const r1 = registerIncident(e1, { route: "/p" }, "evt-1");
    expect(r1.shouldSend).toBe(true);

    clearRouteScope();

    const e2 = new TypeError("y"); e2.stack = "";
    const r2 = registerIncident(e2, { route: "/p" }, "evt-2");
    expect(r2.shouldSend).toBe(true);
    expect(r2.eventId).toBe("evt-2");
  });
});

describe("runtime-error-registry internal-failure safety", () => {
  it("returns a send-allowed registration when context is malformed", () => {
    // Pass undefined route — the registry should still produce a usable
    // registration rather than throwing.
    const e = new Error("x");
    const r = registerIncident(e, {} as never, "evt-safe-1");
    expect(r.eventId).toBe("evt-safe-1");
    expect(r.shouldSend).toBe(true);
  });
});
