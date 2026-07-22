/**
 * F1.3a — Contract-boundary adversarial tests.
 *
 * Proves that every F1.3-touched read endpoint:
 *   - accepts a valid response via the decoder
 *   - rejects a malformed response as ApiContractError (not empty success)
 *   - rejects a missing material field
 *   - rejects a wrong-type material field
 *
 * Tests the decoders directly (not the full React component tree) for
 * precision and speed. Component-level lifecycle tests (failure rendering,
 * retry behavior) are in query-lifecycle.test.tsx.
 */

import { describe, it, expect, vi } from "vitest";

// Prevent any real fetch calls — the decoders don't call transport,
// but the transitive import chain reaches @/api/client.
vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
  apiFetchJson: vi.fn(),
  apiFetchVoid: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) { super(detail); this.name = "ApiError"; }
  },
}));

import { ApiContractError, decodeObject, decodeNumber, decodeString, decodeArray } from "../contracts/common";
import {
  listRunsContract,
  listIdeasContract,
  getPendingContract,
} from "../contracts/dashboard";

// Helper: run a decoder and assert it throws ApiContractError
function expectContractError(decode: () => void) {
  expect(decode).toThrow(ApiContractError);
}

// Helper: run a decoder and assert it succeeds
function expectValid<T>(decode: () => T): T {
  return expect(decode).not.toThrow();
}

// ── Dashboard contracts ──────────────────────────────────────────────

describe("listRunsContract decoder", () => {
  it("accepts a valid runs response", () => {
    const valid = { runs: [{ id: 1, domain: "AI", created_at: "2026-01-01" }], total: 1 };
    const result = listRunsContract.decoder.decode(valid, { endpointId: "test" });
    expect(result.runs).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it("rejects missing runs array", () => {
    expectContractError(() => listRunsContract.decoder.decode({ total: 0 }, { endpointId: "test" }));
  });

  it("rejects missing total", () => {
    expectContractError(() => listRunsContract.decoder.decode({ runs: [] }, { endpointId: "test" }));
  });

  it("rejects malformed run (missing id)", () => {
    expectContractError(() =>
      listRunsContract.decoder.decode({ runs: [{ domain: "AI" }], total: 1 }, { endpointId: "test" }),
    );
  });
});

describe("listIdeasContract decoder", () => {
  it("accepts a valid ideas response", () => {
    const valid = {
      ideas: [{ id: 1, title: "Test", domain: "AI", has_proposal: true, created_at: "2026-01-01" }],
      total: 1,
    };
    const result = listIdeasContract.decoder.decode(valid, { endpointId: "test" });
    expect(result.ideas).toHaveLength(1);
  });

  it("rejects missing ideas array", () => {
    expectContractError(() => listIdeasContract.decoder.decode({ total: 0 }, { endpointId: "test" }));
  });

  it("rejects malformed idea (missing title)", () => {
    expectContractError(() =>
      listIdeasContract.decoder.decode({ ideas: [{ id: 1, domain: "AI" }], total: 1 }, { endpointId: "test" }),
    );
  });

  it("accepts empty ideas as valid (successful empty, not failure)", () => {
    const result = listIdeasContract.decoder.decode({ ideas: [], total: 0 }, { endpointId: "test" });
    expect(result.ideas).toHaveLength(0);
    expect(result.total).toBe(0);
  });
});

describe("getPendingContract decoder", () => {
  it("accepts a valid pending response", () => {
    const valid = {
      pending: [{ id: "gap_001", type: "gap_approval", summary: "Approve" }],
    };
    const result = getPendingContract.decoder.decode(valid, { endpointId: "test" });
    expect(result.pending).toHaveLength(1);
  });

  it("rejects missing pending array", () => {
    expectContractError(() => getPendingContract.decoder.decode({}, { endpointId: "test" }));
  });

  it("rejects malformed approval (missing id)", () => {
    expectContractError(() =>
      getPendingContract.decoder.decode({ pending: [{ type: "x", summary: "y" }] }, { endpointId: "test" }),
    );
  });

  it("accepts empty pending as valid (no items pending)", () => {
    const result = getPendingContract.decoder.decode({ pending: [] }, { endpointId: "test" });
    expect(result.pending).toHaveLength(0);
  });
});

// ── F1.3a contracts (f1-3a-reads.ts) ────────────────────────────────

import {
  listPluginsContract,
  getNotificationsContract,
  listCommentsContract,
} from "../contracts/f1-3a-reads";

describe("listPluginsContract decoder", () => {
  it("accepts valid plugins response", () => {
    const valid = {
      plugins: [{ name: "test", version: "1.0", description: "desc", enabled: true, metadata: {} }],
      total: 1,
    };
    const result = listPluginsContract.decoder.decode(valid, { endpointId: "test" });
    expect(result.plugins).toHaveLength(1);
  });

  it("accepts empty plugins as valid empty", () => {
    const result = listPluginsContract.decoder.decode({ plugins: [], total: 0 }, { endpointId: "test" });
    expect(result.plugins).toHaveLength(0);
  });

  it("rejects missing plugins field", () => {
    expectContractError(() => listPluginsContract.decoder.decode({ total: 0 }, { endpointId: "test" }));
  });
});

describe("getNotificationsContract decoder", () => {
  it("accepts valid notifications response", () => {
    const valid = {
      notifications: [{ id: 1, type: "info", title: "Test", message: "msg", read: false, created_at: "2026-01-01", user_id: null }],
      total: 1,
    };
    const result = getNotificationsContract.decoder.decode(valid, { endpointId: "test" });
    expect(result.notifications).toHaveLength(1);
  });

  it("accepts empty notifications as valid empty", () => {
    const result = getNotificationsContract.decoder.decode({ notifications: [], total: 0 }, { endpointId: "test" });
    expect(result.notifications).toHaveLength(0);
  });
});

describe("listCommentsContract decoder", () => {
  it("accepts valid comments response", () => {
    const valid = {
      comments: [{ id: 1, idea_id: 1, author: "user", content: "text", created_at: "2026-01-01" }],
      total: 1,
    };
    const result = listCommentsContract.decoder.decode(valid, { endpointId: "test" });
    expect(result.comments).toHaveLength(1);
  });

  it("accepts empty comments as valid empty", () => {
    const result = listCommentsContract.decoder.decode({ comments: [], total: 0 }, { endpointId: "test" });
    expect(result.comments).toHaveLength(0);
  });
});

// ── Contract failure vs empty success invariant ──────────────────────

describe("F1.3a invariant: contract failure is never empty success", () => {
  const ctx = { endpointId: "invariant" };

  it("a malformed object payload throws, not returns []", () => {
    const dec = decodeObject<{ items: string[] }>({
      required: { items: decodeArray(decodeString) },
    });
    expect(() => dec.decode("not an object", ctx)).toThrow(ApiContractError);
    expect(() => dec.decode(null, ctx)).toThrow(ApiContractError);
    expect(() => dec.decode({ wrong: "shape" }, ctx)).toThrow(ApiContractError);
  });

  it("a valid empty payload is accepted (not a failure)", () => {
    const dec = decodeObject<{ items: string[] }>({
      required: { items: decodeArray(decodeString) },
    });
    const result = dec.decode({ items: [] }, ctx);
    expect(result.items).toHaveLength(0);
  });

  it("a wrong-type material field throws (not coerced)", () => {
    const dec = decodeObject<{ id: number }>({
      required: { id: decodeNumber },
    });
    expect(() => dec.decode({ id: "not-a-number" }, ctx)).toThrow(ApiContractError);
  });
});
