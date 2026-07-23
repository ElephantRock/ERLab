/**
 * F1.6.1 — canonical runtime-incident registry.
 *
 * Deduplicates reports of the SAME logical incident across channels:
 *   - React error boundary catches it as category=render_error
 *   - window error listener sees it as category=global_error
 * Those MUST produce one transport call, not two.
 *
 * F1.6.1 [V3-1] TWO deduplication mechanisms:
 *
 * 1. Primary: same Error object identity (WeakMap<Error, Record>).
 *    Works when both channels catch the SAME thrown instance — the
 *    common case for render errors that React also surfaces to window.
 *
 * 2. Fallback: category-INDPENDENT fingerprint (error name + route
 *    pathname + safe top frame + short time bucket). Used when two
 *    different Error instances describe the same incident.
 *
 * Category is DELIBERATELY EXCLUDED from the fingerprint — including it
 * would defeat cross-channel deduplication.
 *
 * F1.6.1 [V3-impl-qualification-2]: real TTL with expiry metadata. The
 * fingerprint registry does not grow unboundedly: entries are evicted
 * lazily at registration time, AND the registry size is hard-capped.
 *
 * F1.6.1 [V3-impl-qualification-3]: synchronous composite key. NO async
 * hashing — this is an in-memory deduplication key, not a security
 * primitive. A small synchronous non-cryptographic hash is sufficient.
 *
 * WeakMap entries are GC'd with the Error objects — no permanent
 * suppression of a reused Error.
 */

import { normalizeErrorName, topComponentFrame } from "@/lib/runtime-error-sanitizer";

// ── Types ─────────────────────────────────────────────────────────────

export interface RuntimeIncidentRegistration {
  /** Canonical event_id — reused across channels for the same incident. */
  eventId: string;
  /** False if this incident has already been registered (don't re-send). */
  shouldSend: boolean;
}

interface FingerprintRecord {
  eventId: string;
  expiresAt: number;
}

export interface RegistryContext {
  route: string;
  componentStack?: string;
}

// ── Constants ─────────────────────────────────────────────────────────

/** Incident window for fingerprint deduplication. */
export const INCIDENT_WINDOW_MS = 5_000;

/** Hard cap on fingerprint registry size. Prevents unbounded growth. */
export const MAX_FINGERPRINT_RECORDS = 200;

// ── Synchronous non-cryptographic hash (FNV-1a, 32-bit) ───────────────

function fnv1a32(input: string): string {
  // Standard FNV-1a. Not cryptographic; sufficient for in-memory dedup.
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    // FNV prime (multiply with imul to keep 32-bit semantics).
    h = (h * 0x01000193) >>> 0;
  }
  return h.toString(16);
}

// ── Registries ────────────────────────────────────────────────────────

// Primary: object identity. GC'd when the Error is collected — no
// permanent suppression of a reused Error.
const identityRegistry = new WeakMap<Error, RuntimeIncidentRegistration>();

// Fallback: fingerprint. TTL'd + size-capped.
let fingerprintRegistry = new Map<string, FingerprintRecord>();

// ── Internal helpers ──────────────────────────────────────────────────

function buildFingerprint(
  error: unknown,
  context: RegistryContext,
  now: number,
): string {
  const errorName = normalizeErrorName(error);
  const topFrame = topComponentFrame(context.componentStack);
  const bucket = Math.floor(now / INCIDENT_WINDOW_MS);
  // Category deliberately EXCLUDED.
  return fnv1a32([errorName, context.route, topFrame, bucket].join("|"));
}

function evictExpired(now: number): void {
  if (fingerprintRegistry.size === 0) return;
  // Lazy eviction — drop any expired entry we touch during scan.
  for (const [key, record] of fingerprintRegistry) {
    if (record.expiresAt <= now) {
      fingerprintRegistry.delete(key);
    }
  }
}

function enforceSizeCap(): void {
  // If still over cap after eviction, drop oldest by expiresAt.
  if (fingerprintRegistry.size <= MAX_FINGERPRINT_RECORDS) return;
  const entries = [...fingerprintRegistry.entries()].sort(
    (a, b) => a[1].expiresAt - b[1].expiresAt,
  );
  const drop = entries.length - MAX_FINGERPRINT_RECORDS;
  for (let i = 0; i < drop; i++) {
    const entry = entries[i];
    if (entry) fingerprintRegistry.delete(entry[0]);
  }
}

// ── Public API ────────────────────────────────────────────────────────

/**
 * Register a runtime incident. Returns the canonical event_id and
 * whether this is the first report (shouldSend: true) or a duplicate
 * (shouldSend: false).
 *
 * The caller MUST supply an event_id generator — the registry does not
 * generate IDs itself, so the reporter can pass the same ID it will
 * return synchronously.
 *
 * SYNCHRONOUS. Never throws — wraps all internal logic in try/catch
 * and falls back to "send" on any internal failure (safer to over-send
 * than to lose diagnostics).
 */
export function registerIncident(
  error: unknown,
  context: RegistryContext,
  eventId: string,
): RuntimeIncidentRegistration {
  const now = Date.now();
  const registration: RuntimeIncidentRegistration = { eventId, shouldSend: true };

  try {
    // Primary: object identity.
    if (error instanceof Error) {
      const existing = identityRegistry.get(error);
      if (existing) {
        return { eventId: existing.eventId, shouldSend: false };
      }
    }

    // Fallback: fingerprint.
    evictExpired(now);
    const fingerprint = buildFingerprint(error, context, now);
    const existingFp = fingerprintRegistry.get(fingerprint);
    if (existingFp && existingFp.expiresAt > now) {
      return { eventId: existingFp.eventId, shouldSend: false };
    }

    // First caller wins — register the canonical event_id.
    if (error instanceof Error) {
      identityRegistry.set(error, registration);
    }
    fingerprintRegistry.set(fingerprint, {
      eventId,
      expiresAt: now + INCIDENT_WINDOW_MS,
    });
    enforceSizeCap();
    return registration;
  } catch {
    // Internal failure — safest behavior is to allow the send.
    return registration;
  }
}

/**
 * F1.6.2 route-scope clear. Triggered by RouteErrorBoundary observing
 * location.key changes. Clears the fingerprint registry so a fresh
 * route gets a fresh deduplication window. The WeakMap is left intact
 * (entries are GC'd with the Errors naturally).
 */
export function clearRouteScope(): void {
  fingerprintRegistry = new Map();
}

/**
 * Test-only: reset both registries fully. Used by adversarial tests
 * to prove deduplication works from a clean state.
 */
export function _resetForTesting(): void {
  fingerprintRegistry = new Map();
  // WeakMap cannot be cleared directly — reassign via a fresh binding
  // is not possible (const). Tests use unique Error instances to avoid
  // cross-test contamination.
}

/**
 * Test-only: snapshot the fingerprint registry size. Used to prove the
 * registry does not grow unboundedly.
 */
export function _fingerprintRegistrySizeForTesting(): number {
  return fingerprintRegistry.size;
}
