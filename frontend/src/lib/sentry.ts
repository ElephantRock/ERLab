/**
 * Sentry React SDK initialization.
 *
 * F1.6.3 [V3-5]: Sentry browser automatic capture is DISABLED. The
 * backend diagnostics endpoint (POST /api/v1/diagnostics/runtime-error)
 * is the single governed transport for runtime errors. Leaving Sentry's
 * automatic integrations active would create a parallel transport
 * (GlobalHandlers, unhandled-rejection capture, automatic React boundary
 * capture) that bypasses the governed path and could double-report.
 *
 * `defaultIntegrations: false` disables ALL default browser integrations.
 * `integrations: []` ensures no integration is added. The SDK is
 * essentially dormant; it can later be moved to an internal backend sink
 * without changing the frontend diagnostic contract.
 *
 * The architecture seal (F1.6.4) verifies:
 *   - defaultIntegrations: false present
 *   - integrations: [] present
 *   - zero production Sentry.captureException call sites
 *   - zero production Sentry.captureMessage call sites
 *   - zero Sentry.ErrorBoundary usage
 */
import * as Sentry from "@sentry/react";

export function initSentry(): boolean {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) {
    return false;
  }

  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
    environment: import.meta.env.MODE,
    // F1.6.3 [V3-5]: disable ALL automatic browser integrations so the
    // governed diagnostics endpoint remains the single transport.
    defaultIntegrations: false,
    integrations: [],
  });
  return true;
}

export { Sentry };

