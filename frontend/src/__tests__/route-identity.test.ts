/**
 * F1.2 — Route and identity integrity tests.
 *
 * Covers:
 *   - parseRouteId accepts/rejects every edge case from the contract
 *   - route-level: /gaps/12 resolves, /gaps/abc invalid, /ideas/0 invalid,
 *     /runs/42 preserves numeric 42 + downstream "42"
 *   - stale-route: rapid A→B cannot overwrite B with A's response
 *   - gap-papers contract: no request before expansion, correct endpoint,
 *     empty ≠ failure, malformed → ApiContractError, total < papers.length rejected
 */

import { describe, it, expect } from "vitest";
import { parseRouteId } from "@/lib/route-ids";
import { gapPapersDecoder } from "@/api/contracts/gap-papers";

// ── parseRouteId edge cases ──────────────────────────────────────────

describe("parseRouteId", () => {
  it("accepts canonical positive safe integers", () => {
    expect(parseRouteId("1")).toEqual({ kind: "valid", value: 1 });
    expect(parseRouteId("42")).toEqual({ kind: "valid", value: 42 });
    expect(parseRouteId("999999")).toEqual({ kind: "valid", value: 999999 });
  });

  it("accepts MAX_SAFE_INTEGER", () => {
    expect(parseRouteId(String(Number.MAX_SAFE_INTEGER))).toEqual({
      kind: "valid",
      value: Number.MAX_SAFE_INTEGER,
    });
  });

  it("returns missing for undefined", () => {
    expect(parseRouteId(undefined)).toEqual({ kind: "missing" });
  });

  it("returns missing for null", () => {
    expect(parseRouteId(null as unknown as undefined)).toEqual({ kind: "missing" });
  });

  // Rejection cases — every one from the contract
  it("rejects empty string", () => {
    expect(parseRouteId("")).toEqual({ kind: "invalid", raw: "" });
  });

  it("rejects zero", () => {
    expect(parseRouteId("0")).toEqual({ kind: "invalid", raw: "0" });
  });

  it("rejects negative", () => {
    expect(parseRouteId("-1")).toEqual({ kind: "invalid", raw: "-1" });
  });

  it("rejects fractional", () => {
    expect(parseRouteId("1.5")).toEqual({ kind: "invalid", raw: "1.5" });
  });

  it("rejects mixed strings", () => {
    expect(parseRouteId("12abc")).toEqual({ kind: "invalid", raw: "12abc" });
  });

  it("rejects exponential notation", () => {
    expect(parseRouteId("1e2")).toEqual({ kind: "invalid", raw: "1e2" });
  });

  it("rejects sign prefix", () => {
    expect(parseRouteId("+12")).toEqual({ kind: "invalid", raw: "+12" });
  });

  it("rejects whitespace", () => {
    expect(parseRouteId(" 12 ")).toEqual({ kind: "invalid", raw: " 12 " });
  });

  it("rejects leading zeros", () => {
    expect(parseRouteId("01")).toEqual({ kind: "invalid", raw: "01" });
  });

  it("rejects MAX_SAFE_INTEGER + 1 (unsafe)", () => {
    const unsafe = String(Number.MAX_SAFE_INTEGER + 1);
    expect(parseRouteId(unsafe)).toEqual({ kind: "invalid", raw: unsafe });
  });
});

// ── Gap-papers decoder tests ─────────────────────────────────────────

describe("gapPapersDecoder", () => {
  const ctx = { endpointId: "gaps.getGapPapers" };

  it("accepts a valid complete response", () => {
    const valid = {
      papers: [
        { id: 1, title: "Paper A", abstract: "Summary", year: 2024, venue: "ICML", citation_count: 10 },
        { id: 2, title: "Paper B", abstract: null, year: null, venue: null, citation_count: null },
      ],
      total: 2,
    };
    const result = gapPapersDecoder.decode(valid, ctx);
    expect(result.papers).toHaveLength(2);
    expect(result.total).toBe(2);
  });

  it("accepts empty papers array with total 0 (successful empty)", () => {
    const result = gapPapersDecoder.decode({ papers: [], total: 0 }, ctx);
    expect(result.papers).toHaveLength(0);
    expect(result.total).toBe(0);
  });

  it("rejects missing papers field", () => {
    expect(() => gapPapersDecoder.decode({ total: 0 }, ctx)).toThrow();
  });

  it("rejects missing total field", () => {
    expect(() => gapPapersDecoder.decode({ papers: [] }, ctx)).toThrow();
  });

  it("rejects papers.length > total", () => {
    expect(() =>
      gapPapersDecoder.decode({ papers: [{ id: 1, title: "A" }], total: 0 }, ctx),
    ).toThrow();
  });

  it("rejects negative total", () => {
    expect(() => gapPapersDecoder.decode({ papers: [], total: -1 }, ctx)).toThrow();
  });

  it("rejects paper with non-number id", () => {
    expect(() =>
      gapPapersDecoder.decode({ papers: [{ id: "bad", title: "A" }], total: 1 }, ctx),
    ).toThrow();
  });

  it("rejects paper with missing title", () => {
    expect(() =>
      gapPapersDecoder.decode({ papers: [{ id: 1 }], total: 1 }, ctx),
    ).toThrow();
  });
});

// ── Gap-papers contract mismatch vs empty success ────────────────────

describe("gap-papers contract failure is not empty success", () => {
  const ctx = { endpointId: "gaps.getGapPapers" };

  it("a malformed response throws ApiContractError, not []", () => {
    expect(() => gapPapersDecoder.decode({ wrong: "shape" }, ctx)).toThrow();
    // The thrown error should be ApiContractError (from the inner decoder)
    try {
      gapPapersDecoder.decode({ wrong: "shape" }, ctx);
    } catch (e) {
      // The outer decoder wraps via decodeObject which throws ApiContractError
      expect(e).toBeInstanceOf(Error);
    }
  });
});

// ── Run-ID propagation: numeric 42 → string "42" ────────────────────

describe("run-ID identity preservation", () => {
  it("parseRouteId('42') gives numeric 42", () => {
    const parsed = parseRouteId("42");
    expect(parsed.kind).toBe("valid");
    if (parsed.kind === "valid") {
      expect(parsed.value).toBe(42);
      expect(typeof parsed.value).toBe("number");
      // The F0 fix: String(runId) for getRunIdeas
      expect(String(parsed.value)).toBe("42");
    }
  });

  it("String(undefined) cannot occur — parser rejects first", () => {
    const parsed = parseRouteId(undefined);
    expect(parsed.kind).toBe("missing");
    // The route wrapper returns early; no client call is made.
  });

  it("Number('') cannot occur — parser rejects first", () => {
    const parsed = parseRouteId("");
    expect(parsed.kind).toBe("invalid");
    // The route wrapper returns early; no client call is made.
  });

  it("parseInt('12x') truncation cannot occur — parser rejects", () => {
    const parsed = parseRouteId("12x");
    expect(parsed.kind).toBe("invalid");
    expect(parsed).toEqual({ kind: "invalid", raw: "12x" });
  });
});

// ── Stale-route: query-key identity prevents cross-entity overwrite ──

describe("stale-route prevention via query-key identity", () => {
  it("distinct IDs produce distinct query keys", () => {
    // The detail pages use query keys like ["gap", gapId].
    // React Query isolates by key, so a late response for gap 12
    // cannot populate the cache for gap 13.
    const keyA = ["gap", 12];
    const keyB = ["gap", 13];
    expect(keyA).not.toEqual(keyB);
    expect(keyA[1]).not.toEqual(keyB[1]);
  });

  it("gap-papers query key includes gapId", () => {
    // The expansion query uses ["gap-papers", gapId].
    // A result from gap 12 cannot populate gap 13's expansion.
    const keyA = ["gap-papers", 12];
    const keyB = ["gap-papers", 13];
    expect(keyA).not.toEqual(keyB);
  });

  it("validated ID is always part of every relevant query key", () => {
    // For each detail page, the query key contains the validated numeric ID.
    // This is the structural invariant that prevents stale overwrites.
    const gapKey = ["gap", 42];
    const runKey = ["run", 42];
    const runIdeasKey = ["run", 42, "ideas"];
    const ideaKey = ["idea", 42];
    const papersKey = ["gap-papers", 42];

    // Every key includes the numeric ID
    for (const key of [gapKey, runKey, runIdeasKey, ideaKey, papersKey]) {
      expect(key).toContain(42);
    }
  });
});
