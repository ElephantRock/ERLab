/**
 * F1.2 — Centralized route-parameter parser.
 *
 * Every page that receives an entity ID from a URL parameter must use
 * `parseRouteId` instead of `Number(params.id)` / `parseInt`. The parser
 * uses a strict canonical positive-decimal grammar to reject every
 * coercion edge case, and returns a discriminated union so the caller
 * can pattern-match into the correct UI posture.
 *
 * Canonical grammar: `/^[1-9]\d*$/` — only strings like "1", "12", "999".
 * This rejects noncanonical representations such as "01" (prevents
 * multiple URLs from silently resolving to the same identity), and all
 * non-numeric / mixed strings.
 */

/** Result of parsing a route parameter into a validated entity ID. */
export type RouteIdResult =
  | { kind: "valid"; value: number }
  | { kind: "missing" }
  | { kind: "invalid"; raw: string };

/** Strict canonical positive-decimal: first digit 1-9, rest 0-9, no leading zeros. */
const POSITIVE_ROUTE_ID = /^[1-9]\d*$/;

/**
 * Parse a route parameter string into a validated entity ID.
 *
 * Rejects: undefined, empty, "0", "-1", "1.5", "12abc", "1e2", "+12",
 * " 12 ", "01", values above Number.MAX_SAFE_INTEGER, Infinity, NaN.
 *
 * Returns:
 *   { kind: "valid", value: N } — safe positive integer, ready for use
 *   { kind: "missing" }         — parameter was undefined
 *   { kind: "invalid", raw: S } — parameter was present but malformed
 */
export function parseRouteId(raw: string | undefined): RouteIdResult {
  if (raw === undefined || raw === null) {
    return { kind: "missing" };
  }
  if (!POSITIVE_ROUTE_ID.test(raw)) {
    return { kind: "invalid", raw };
  }
  const value = Number(raw);
  if (!Number.isSafeInteger(value)) {
    return { kind: "invalid", raw };
  }
  return { kind: "valid", value };
}
