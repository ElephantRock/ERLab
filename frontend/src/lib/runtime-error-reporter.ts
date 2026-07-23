/**
 * F1.6.1 — never-throw runtime-error reporter.
 *
 * F1.6.1 [V3-impl-qualification-1]: reportRuntimeError is a TOTAL
 * FUNCTION. It must never propagate an exception — not from
 * registerIncident, not from sanitizeErrorForReport, not from event-id
 * generation, not from sendRuntimeErrorReport invocation. Every
 * invocation returns an event_id (the fallback if anything inside
 * fails).
 *
 * The transport (sendRuntimeErrorReport) is asynchronous and may reject;
 * the reporter swallows all transport failures.
 *
 * F1.6.1 [V3-2]: reportRuntimeError is SYNCHRONOUS and returns the
 * event_id immediately so a React class boundary can place it in state
 * and render it in the fallback without awaiting transport.
 *
 * F1.6.1 [C4 from v2 review]: AbortError and intentional-cancellation
 * errors are filtered at the reporter layer — the reporter still returns
 * an event_id (so the caller has a stable handle) but does NOT send.
 * ApiError and ApiContractError are NOT blanket-suppressed — if one
 * reaches the reporter via a global observer, it indicates an unhandled
 * programming path and SHOULD be reported.
 */

import { sendRuntimeErrorReport } from "@/api/clients/diagnostics-client";
import type { RuntimeErrorCode } from "@/api/contracts/diagnostics";
import {
  sanitizeErrorForReport,
  type SanitizerContext,
} from "@/lib/runtime-error-sanitizer";
import {
  registerIncident,
  type RegistryContext,
} from "@/lib/runtime-error-registry";

// ── Types ─────────────────────────────────────────────────────────────

export interface RuntimeErrorContext {
  category: RuntimeErrorCode;
  route: string;
  componentStack?: string;
  /** Optional correlation ID captured from response headers. */
  correlationId?: string;
}

// ── Event ID generation (synchronous, never throws) ───────────────────

/**
 * Generate a stable event ID client-side. Uses crypto.randomUUID when
 * available (modern browsers, jsdom); falls back to a timestamp+random
 * composite for older environments. NEVER throws.
 */
export function generateEventId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return `evt-${crypto.randomUUID()}`;
    }
  } catch {
    // fall through to fallback
  }
  // Fallback: timestamp + random. Bounded to safe-charset.
  const ts = Date.now().toString(36);
  const rnd = Math.random().toString(36).slice(2, 10);
  return `evt-${ts}-${rnd}`;
}

// ── AbortError filter (C4) ────────────────────────────────────────────

/**
 * True for AbortError (name check) and intentional-cancellation errors
 * carrying an explicit __handled marker. These are EXPECTED and must NOT
 * be reported.
 *
 * ApiError and ApiContractError are NOT filtered here — they ARE
 * reported if they reach the reporter via a global observer. Expected
 * query/mutation failures never reach global observers because TanStack
 * catches them into query.error/mutation.error locally (proven by
 * adversarial tests in F1.6.4).
 */
export function isFilteredError(error: unknown): boolean {
  try {
    if (error instanceof Error) {
      if (error.name === "AbortError") return true;
      // Future hook: intentional-cancellation marker.
      if ((error as Error & { __handled?: boolean }).__handled === true) return true;
    }
    // DOMException with name AbortError (older call sites).
    if (typeof DOMException !== "undefined" && error instanceof DOMException) {
      if (error.name === "AbortError") return true;
    }
  } catch {
    // ignore
  }
  return false;
}

// ── Build version (compile-time injection) ────────────────────────────

/**
 * F1.6.1 [V3-impl-qualification-4]: production build identifier. The
 * lazy-retry marker MUST NOT key on a permanent "unknown" build — that
 * could suppress guarded recovery for subsequent deployments in the
 * same browser session.
 *
 * Vite injects VITE_BUILD_HASH at build time. CI/build test fails when
 * this is absent in production builds. In dev mode the value is "dev"
 * (timestamped via occurred_at so reports stay distinguishable).
 */
function getBuildVersion(): string | undefined {
  try {
    const v = (import.meta.env.VITE_BUILD_HASH as string | undefined) ?? undefined;
    if (v && v !== "unknown") return v;
    // Dev mode — distinguishable but not a permanent suppression key.
    if (import.meta.env.DEV) return "dev";
    return undefined;
  } catch {
    return undefined;
  }
}

// ── Public reporter (TOTAL FUNCTION — never throws) ───────────────────

/**
 * Report a runtime error. SYNCHRONOUS — returns the canonical event_id
 * immediately so callers (class boundaries, observers) can render or log
 * it without awaiting transport. The actual HTTP send is fire-and-forget
 * and any failure is swallowed.
 *
 * Behavior:
 *   - AbortError / intentional cancellation → returns event_id, does NOT send
 *   - First occurrence of an incident → sends once
 *   - Duplicate (same Error identity or same fingerprint within window)
 *     → returns canonical event_id, does NOT re-send
 *   - Any internal failure → returns a fallback event_id, never throws
 */
export function reportRuntimeError(
  error: unknown,
  context: RuntimeErrorContext,
): string {
  // Always generate a fallback FIRST so any internal failure still
  // produces a usable event_id.
  const fallbackEventId = generateEventId();

  try {
    // Register the incident — this returns the canonical event_id
    // (possibly reusing one from a prior channel that caught the same
    // incident). It also tells us whether this is the first report.
    const registryContext: RegistryContext = {
      route: context.route,
      componentStack: context.componentStack,
    };
    const incident = registerIncident(error, registryContext, fallbackEventId);

    // AbortError / intentional cancellation: do NOT send, but still
    // return the event_id so the caller has a stable handle.
    if (isFilteredError(error)) {
      return incident.eventId;
    }

    if (!incident.shouldSend) {
      // Duplicate of an already-reported incident in this window.
      return incident.eventId;
    }

    // Build the sanitized report. This is wrapped in its own try/catch
    // so a sanitizer failure does not prevent the event_id from being
    // returned.
    try {
      const sanitizerContext: SanitizerContext = {
        category: context.category,
        route: context.route,
        componentStack: context.componentStack,
        correlationId: context.correlationId,
        buildVersion: getBuildVersion(),
      };
      const report = sanitizeErrorForReport(error, sanitizerContext, incident.eventId);

      // Fire-and-forget transport. Any rejection is swallowed so the
      // application never observes a reporting failure (which could
      // itself trigger an unhandledrejection event and recurse).
      void sendRuntimeErrorReport(report).catch(() => {
        // Reporting must never affect application execution.
      });
    } catch {
      // Sanitizer or transport invocation failed synchronously.
      // The event_id was already registered; the caller still has it.
    }

    return incident.eventId;
  } catch {
    // Any unexpected internal failure — return the fallback.
    return fallbackEventId;
  }
}
