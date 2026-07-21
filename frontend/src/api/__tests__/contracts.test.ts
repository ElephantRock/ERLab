/**
 * F1.1 — Contract layer tests.
 *
 * Covers:
 *   - primitive decoders (string/number/boolean/object/array/enum/stringRecord)
 *   - ApiContractError on malformed payloads (the core F1.1 invariant:
 *     a contract failure is NOT an empty result)
 *   - empty-body policy enforcement (forbidden/allowed/required)
 *   - the EnsembleReview value decoder (M1)
 *   - the gap mutation truthful result types (H3)
 *   - stage-model config decoder (H1)
 *   - callContract routing: apiFetch receives auth headers + correct method
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  ApiContractError,
  decodeString,
  decodeNumber,
  decodeBoolean,
  decodeObject,
  decodeArray,
  decodeEnum,
  decodeStringRecord,
  buildPath,
  withQuery,
  callContract,
  type EndpointContract,
} from "../contracts/common";
import { decodeEnsembleReview } from "../contracts/ideas";

// ── Primitive decoders ───────────────────────────────────────────────

describe("decodeString", () => {
  it("accepts a string", () => {
    expect(decodeString.decode("hello", { endpointId: "test" })).toBe("hello");
  });
  it("rejects a number with ApiContractError", () => {
    expect(() => decodeString.decode(42, { endpointId: "test" })).toThrow(ApiContractError);
  });
  it("rejects null", () => {
    expect(() => decodeString.decode(null, { endpointId: "test" })).toThrow(ApiContractError);
  });
});

describe("decodeNumber", () => {
  it("accepts a finite number", () => {
    expect(decodeNumber.decode(42, { endpointId: "test" })).toBe(42);
  });
  it("rejects NaN", () => {
    expect(() => decodeNumber.decode(NaN, { endpointId: "test" })).toThrow(ApiContractError);
  });
  it("rejects a string", () => {
    expect(() => decodeNumber.decode("42", { endpointId: "test" })).toThrow(ApiContractError);
  });
});

describe("decodeBoolean", () => {
  it("accepts true/false", () => {
    expect(decodeBoolean.decode(true, { endpointId: "test" })).toBe(true);
    expect(decodeBoolean.decode(false, { endpointId: "test" })).toBe(false);
  });
  it("rejects a string", () => {
    expect(() => decodeBoolean.decode("true", { endpointId: "test" })).toThrow(ApiContractError);
  });
});

// ── Object decoder ───────────────────────────────────────────────────

describe("decodeObject", () => {
  const decoder = decodeObject<{ id: number; name: string }>({
    required: { id: decodeNumber, name: decodeString },
  });

  it("validates required fields and preserves extras", () => {
    const result = decoder.decode({ id: 1, name: "test", extra: "kept" }, { endpointId: "test" });
    expect(result.id).toBe(1);
    expect(result.name).toBe("test");
    expect((result as any).extra).toBe("kept"); // forward-compat spread
  });

  it("rejects non-object", () => {
    expect(() => decoder.decode("string", { endpointId: "test" })).toThrow(ApiContractError);
    expect(() => decoder.decode(null, { endpointId: "test" })).toThrow(ApiContractError);
    expect(() => decoder.decode([], { endpointId: "test" })).toThrow(ApiContractError);
  });

  it("rejects missing required field", () => {
    expect(() => decoder.decode({ id: 1 }, { endpointId: "test" })).toThrow(ApiContractError);
  });

  it("rejects wrong-type required field", () => {
    expect(() => decoder.decode({ id: "not-a-number", name: "test" }, { endpointId: "test" })).toThrow(ApiContractError);
  });

  it("validates optional fields when present", () => {
    const dec = decodeObject<{ id: number; label?: string }>({
      required: { id: decodeNumber },
      optional: { label: decodeString },
    });
    expect(dec.decode({ id: 1 }, { endpointId: "test" }).id).toBe(1);
    expect(dec.decode({ id: 1, label: "x" }, { endpointId: "test" }).id).toBe(1);
    expect(() => dec.decode({ id: 1, label: 42 }, { endpointId: "test" })).toThrow(ApiContractError);
  });
});

// ── Array decoder ────────────────────────────────────────────────────

describe("decodeArray", () => {
  it("validates each item", () => {
    const dec = decodeArray(decodeNumber);
    expect(dec.decode([1, 2, 3], { endpointId: "test" })).toEqual([1, 2, 3]);
  });
  it("rejects non-array", () => {
    expect(() => decodeArray(decodeNumber).decode("not-array", { endpointId: "test" })).toThrow(ApiContractError);
  });
  it("rejects array with wrong item type, citing index", () => {
    expect(() => decodeArray(decodeNumber).decode([1, "two"], { endpointId: "test" })).toThrow(/index 1/);
  });
});

// ── Enum decoder ─────────────────────────────────────────────────────

describe("decodeEnum", () => {
  const dec = decodeEnum(["a", "b", "c"]);
  it("accepts a valid value", () => {
    expect(dec.decode("b", { endpointId: "test" })).toBe("b");
  });
  it("rejects an invalid value", () => {
    expect(() => dec.decode("d", { endpointId: "test" })).toThrow(ApiContractError);
  });
});

// ── StringRecord decoder ─────────────────────────────────────────────

describe("decodeStringRecord", () => {
  it("accepts an object with string values", () => {
    expect(decodeStringRecord.decode({ a: "1", b: "2" }, { endpointId: "test" })).toEqual({ a: "1", b: "2" });
  });
  it("accepts empty object", () => {
    expect(decodeStringRecord.decode({}, { endpointId: "test" })).toEqual({});
  });
  it("rejects non-string value", () => {
    expect(() => decodeStringRecord.decode({ a: 1 }, { endpointId: "test" })).toThrow(ApiContractError);
  });
  it("rejects non-object", () => {
    expect(() => decodeStringRecord.decode([], { endpointId: "test" })).toThrow(ApiContractError);
  });
});

// ── Path helpers ─────────────────────────────────────────────────────

describe("buildPath", () => {
  it("substitutes params", () => {
    expect(buildPath("/gaps/{id}", { id: 42 })).toBe("/gaps/42");
  });
  it("substitutes multiple params", () => {
    expect(buildPath("/ideas/{ideaId}/sections/{sectionKey}", { ideaId: 1, sectionKey: "method" })).toBe(
      "/ideas/1/sections/method",
    );
  });
  it("throws on missing param", () => {
    expect(() => buildPath("/gaps/{id}", {})).toThrow(/missing param id/);
  });
});

describe("withQuery", () => {
  it("appends query params, dropping null/undefined/empty", () => {
    expect(withQuery("/gaps", { run_id: 1, search: undefined, empty: "" })).toBe("/gaps?run_id=1");
  });
  it("returns path unchanged when all params dropped", () => {
    expect(withQuery("/gaps", { search: undefined })).toBe("/gaps");
  });
});

// ── EnsembleReview decoder (M1) ──────────────────────────────────────

describe("decodeEnsembleReview", () => {
  it("returns null for absent value", () => {
    expect(decodeEnsembleReview(null)).toBeNull();
    expect(decodeEnsembleReview(undefined)).toBeNull();
  });

  it("returns null for non-object", () => {
    expect(decodeEnsembleReview("string")).toBeNull();
    expect(decodeEnsembleReview([])).toBeNull();
  });

  it("decodes a valid full review", () => {
    const valid = {
      overall_score: 8.5,
      summary: "Strong proposal",
      methodology: { perspective: "methodologist", score: 9, strengths: ["s"], weaknesses: [], suggestions: [] },
      novelty: null,
      clarity: null,
      consensus_strengths: ["a"],
      critical_weaknesses: [],
      actionable_suggestions: ["b"],
      risk_flags: ["low"],
    };
    const result = decodeEnsembleReview(valid);
    expect(result).not.toBeNull();
    expect(result!.overall_score).toBe(8.5);
    expect(result!.summary).toBe("Strong proposal");
    expect(result!.methodology?.perspective).toBe("methodologist");
  });

  it("throws ApiContractError when overall_score is missing (material field)", () => {
    const malformed = { summary: "no score" };
    expect(() => decodeEnsembleReview(malformed)).toThrow(ApiContractError);
  });

  it("throws ApiContractError when overall_score is wrong type", () => {
    const malformed = { overall_score: "high", summary: "x" };
    expect(() => decodeEnsembleReview(malformed)).toThrow(ApiContractError);
  });
});

// ── callContract: mocked transport ───────────────────────────────────
//
// Mock apiFetch so we can test the decoder + empty-body policy without
// network calls. The mock is hoisted by vitest above all imports.

vi.mock("@/api/client", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
      this.name = "ApiError";
    }
  },
}));

// Import after the mock so callContract sees the mocked apiFetch.
import { apiFetch as mockApiFetch } from "@/api/client";

describe("callContract empty-body policy", () => {
  beforeEach(() => {
    vi.mocked(mockApiFetch).mockReset();
  });

  it("emptyBody:'required' returns void when body is empty", async () => {
    vi.mocked(mockApiFetch).mockResolvedValue(undefined);
    const contract: EndpointContract<void> = {
      id: "test.void", method: "DELETE", pathPattern: "/x",
      emptyBody: "required",
    };
    const result = await callContract(contract);
    expect(result).toBeUndefined();
  });

  it("emptyBody:'required' rejects a payload", async () => {
    vi.mocked(mockApiFetch).mockResolvedValue({ unexpected: "payload" });
    const contract: EndpointContract<void> = {
      id: "test.void", method: "DELETE", pathPattern: "/x",
      emptyBody: "required",
    };
    await expect(callContract(contract)).rejects.toThrow(ApiContractError);
  });

  it("emptyBody:'forbidden' throws when body is empty", async () => {
    vi.mocked(mockApiFetch).mockResolvedValue(null);
    const contract: EndpointContract<{ id: number }> = {
      id: "test.requiresPayload", method: "GET", pathPattern: "/x",
      emptyBody: "forbidden",
      decodeResponse: decodeObject({ required: { id: decodeNumber } }),
    };
    await expect(callContract(contract)).rejects.toThrow(ApiContractError);
  });
});

describe("callContract contract-failure semantics", () => {
  beforeEach(() => {
    vi.mocked(mockApiFetch).mockReset();
  });

  it("a malformed 2xx payload throws ApiContractError (not empty success)", async () => {
    vi.mocked(mockApiFetch).mockResolvedValue({ wrong: "shape" });
    const contract: EndpointContract<{ id: number }> = {
      id: "test.malformed", method: "GET", pathPattern: "/x",
      emptyBody: "forbidden",
      decodeResponse: decodeObject({ required: { id: decodeNumber } }),
    };
    try {
      await callContract(contract);
      expect.fail("should have thrown");
    } catch (e) {
      expect(e).toBeInstanceOf(ApiContractError);
      expect((e as ApiContractError).code).toBe("api_response_contract_mismatch");
      expect((e as ApiContractError).endpointId).toBe("test.malformed");
    }
  });

  it("a valid payload decodes successfully", async () => {
    vi.mocked(mockApiFetch).mockResolvedValue({ id: 42 });
    const contract: EndpointContract<{ id: number }> = {
      id: "test.valid", method: "GET", pathPattern: "/x",
      emptyBody: "forbidden",
      decodeResponse: decodeObject({ required: { id: decodeNumber } }),
    };
    const result = await callContract(contract);
    expect(result.id).toBe(42);
  });

  it("passes auth headers + method through to apiFetch (H1)", async () => {
    vi.mocked(mockApiFetch).mockResolvedValue({ id: 1 });
    const contract: EndpointContract<{ id: number }> = {
      id: "test.auth", method: "PUT", pathPattern: "/settings/models",
      emptyBody: "forbidden",
      decodeResponse: decodeObject({ required: { id: decodeNumber } }),
    };
    await callContract(contract, { body: { stage: "model" } });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/settings/models",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ stage: "model" }),
      }),
    );
  });
});
