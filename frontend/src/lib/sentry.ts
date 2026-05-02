/**
 * Sentry React SDK initialization (BATCH-52).
 * Only initializes when VITE_SENTRY_DSN env var is set.
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
  });
  return true;
}

export { Sentry };
